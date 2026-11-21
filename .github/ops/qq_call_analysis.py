import capstone, json, re, bisect
def analyze(binary, meta):
    data=binary.read_bytes(); im=meta.Image(data)
    meta.SELECTED=re.compile(r"(?:QQAVTinyVideoRecorder|QAVRecordPanel|QQAVMorePanelViewModel|QQRTC.*Record.*)")
    meta.SELECTOR=re.compile(r"record|captur",re.I)
    methods=im.inspect()
    selectors={m["selector"] for m in methods}
    labels={int(m["imp"],16):m["class"]+" "+m["selector"] for m in methods}
    chosen=[m for m in methods if re.search(r"record|captur",m["selector"],re.I) and re.search(r"send|notify|notice|remind",m["selector"],re.I)]
    focused=[m for m in methods if m["class"] in ("QQAVTinyVideoRecorder","QAVRecordPanel","QQAVMorePanelViewModel","QQRTCP2PRecordPart") and re.search(r"record",m["selector"],re.I)]
    output=[]
    dis=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)
    def stub(target):
        try:
            off,_=im.location(target,32); regs={}
            for ins in dis.disasm(data[off:off+32],target):
                op=ins.op_str
                ma=re.fullmatch(r"(x\d+), #?(0x[0-9a-f]+)",op)
                if ins.mnemonic=="adrp" and ma: regs[ma[1]]=int(ma[2],16)
                ml=re.fullmatch(r"x1, \[(x\d+)(?:, #(0x[0-9a-f]+|\d+))?\]",op)
                if ins.mnemonic=="ldr" and ml and ml[1] in regs:
                    s=im.string(im.pointer(regs[ml[1]]+int(ml[2] or "0",0)))
                    if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9:]{0,200}",s): return "objc="+s
        except meta.MetadataError: pass
        return ""
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
            if ins.mnemonic in ("bl","b"):
                try: comment=labels.get(int(op.lstrip("#"),16)) or stub(int(op.lstrip("#"),16)) or comment
                except ValueError: pass
            rows.append(hex(ins.address)+" "+ins.mnemonic+" "+op+(" ; "+comment if comment else ""))
        output.append({"method":m,"assembly":rows})
    return {"notification_candidates":chosen,"focused_methods":focused,"analysis":output}
