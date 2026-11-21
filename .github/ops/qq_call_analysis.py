import capstone, json, re, bisect
def analyze(binary, meta):
    data=binary.read_bytes(); im=meta.Image(data)
    meta.SELECTED=re.compile(r"(?:QQAVTinyVideoRecorder|QAVRecordPanel|QQAVMorePanelViewModel|QQRTC.*Record.*|QQAVRecordBar|QQAVRecordCircleButton)")
    meta.SELECTOR=re.compile(r"record|captur|^playAudio:andLoopTime:$",re.I)
    methods=im.inspect()
    selectors={m["selector"] for m in methods}
    labels={int(m["imp"],16):m["class"]+" "+m["selector"] for m in methods}
    chosen=[m for m in methods if re.search(r"record|captur",m["selector"],re.I) and re.search(r"send|notify|notice|remind",m["selector"],re.I)]
    focused=[m for m in methods if m["class"] in ("QQAVTinyVideoRecorder","QQRTCP2PRecordPart") or m["selector"]=="playAudio:andLoopTime:"]
    focused.append({"class":"bounded_helper","selector":"recordAudioHelper","types":"disassembly_only","imp":"0x1106a30b4"})
    output=[]
    dis=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)
    def stub(target,depth=0):
        if depth>3: return ""
        try:
            off,_=im.location(target,32); regs={}
            for ins in dis.disasm(data[off:off+32],target):
                op=ins.op_str
                if ins.address==target and ins.mnemonic=="b":
                    return stub(int(op.lstrip("#"),16),depth+1)
                ma=re.fullmatch(r"(x\d+), #?(0x[0-9a-f]+)",op)
                if ins.mnemonic=="adrp" and ma: regs[ma[1]]=int(ma[2],16)
                ml=re.fullmatch(r"x1, \[(x\d+)(?:, #(0x[0-9a-f]+|\d+))?\]",op)
                if ins.mnemonic=="ldr" and ml and ml[1] in regs:
                    s=im.string(im.pointer(regs[ml[1]]+int(ml[2] or "0",0)))
                    if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9:]{0,200}",s): return "objc="+s
        except meta.MetadataError: pass
        return ""
    def constant(address):
        if not any(n=="__cfstring" and a<=address and address+32<=a+s for n,a,s in im.sections): return ""
        try:
            length=im.integer(address+24,"<Q")
            if not 0<length<=160: return ""
            flags=im.integer(address+8,"<Q")
            ptr=im.pointer(address+16)
            wide=bool(flags&0x10)
            off,_=im.location(ptr,length*(2 if wide else 1))
            value=data[off:off+length*(2 if wide else 1)].decode("utf-16-le" if wide else "utf-8")
            if any(ord(c)<32 for c in value): return ""
            return "cfstring="+value
        except (meta.MetadataError,UnicodeError): return ""
    addresses=sorted(labels)
    for m in focused+chosen:
        addr=int(m["imp"],16)
        if addr<0x100000000: continue
        idx=bisect.bisect_right(addresses,addr)
        end=min(addresses[idx] if idx<len(addresses) else addr+4096,addr+4096)
        off,_=im.location(addr,end-addr)
        regs={}; rows=[]
        for ins in dis.disasm(data[off:off+end-addr],addr):
            op=ins.op_str; comment=""
            match=re.fullmatch(r"(x\d+), #?(0x[0-9a-f]+)",op)
            if ins.mnemonic=="adrp" and match: regs[match[1]]=int(match[2],16)
            ma=re.fullmatch(r"(x\d+), (x\d+), #(0x[0-9a-f]+|\d+)",op)
            if ins.mnemonic=="add" and ma and ma[2] in regs: regs[ma[1]]=regs[ma[2]]+int(ma[3],0)
            ml=re.fullmatch(r"(x\d+), \[(x\d+)(?:, #(0x[0-9a-f]+|\d+))?\]",op)
            if ins.mnemonic=="ldr" and ml and ml[2] in regs:
                p=regs[ml[2]]+int(ml[3] or "0",0)
                try:
                    target=im.pointer(p); regs[ml[1]]=target
                    s=im.string(target)
                    if s in selectors: comment="selector="+s
                except meta.MetadataError: pass
            if ins.mnemonic in ("adrp","add","ldr"):
                reg=op.split(",")[0]
                if reg in regs: comment=constant(regs[reg]) or comment
            if ins.mnemonic in ("bl","b"):
                try: comment=labels.get(int(op.lstrip("#"),16)) or stub(int(op.lstrip("#"),16)) or comment
                except ValueError: pass
            rows.append(hex(ins.address)+" "+ins.mnemonic+" "+op+(" ; "+comment if comment else ""))
        output.append({"method":m,"assembly":rows})
    stubs=[]
    for addr in (0x1178793f4,0x1178fbc7c,0x11793216c,0x117963da8,0x1106e28f4):
        off,_=im.location(addr,96)
        stubs.append({"address":hex(addr),"resolved":stub(addr),"instructions":[i.mnemonic+" "+i.op_str for i in dis.disasm(data[off:off+96],addr)]})
    table,_=im.location(0x125b07c90,9)
    routes={str(i+1):hex(0x1106a0c28+data[table+i]*4) for i in range(9)}
    return {"notification_candidates":chosen,"focused_methods":focused,"analysis":output,"stubs":stubs,"peer_state_routes":routes}
