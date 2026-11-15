"""Bounded static disassembly of two inspected QQ methods; no execution."""
import json,mmap
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
from capstone.arm64 import ARM64_OP_IMM,ARM64_OP_REG,ARM64_OP_MEM
from objc_metadata import Image
def inspect_device(path):
    with open(path,"rb") as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as data:
        image=Image(data); decoder=Cs(CS_ARCH_ARM64,CS_MODE_ARM);decoder.detail=True
        for label,address,size in [("NTSettingService.getDeviceName",0x109e78e58,0xec),("OnlineStatusModule.openCustomDeviceNameWeb",0x10fa115d4,0x144)]:
            offset,_=image.location(address,size); regs={}; out=[]
            for ins in decoder.disasm(data[offset:offset+size],address):
                ops=ins.operands; annotations=[]
                if ins.mnemonic=="adrp" and len(ops)==2: regs[ops[0].reg]=ops[1].imm
                elif ins.mnemonic=="add" and len(ops)==3 and ops[2].type==ARM64_OP_IMM and ops[1].reg in regs:
                    regs[ops[0].reg]=regs[ops[1].reg]+ops[2].imm
                elif ins.mnemonic=="ldr" and len(ops)==2 and ops[1].type==ARM64_OP_MEM and ops[1].mem.base in regs:
                    ptr=regs[ops[1].mem.base]+ops[1].mem.disp
                    try: regs[ops[0].reg]=image.pointer(ptr)
                    except Exception: regs.pop(ops[0].reg,None)
                elif ins.mnemonic=="mov" and len(ops)==2 and ops[1].type==ARM64_OP_REG and ops[1].reg in regs:
                    regs[ops[0].reg]=regs[ops[1].reg]
                for value in list(regs.values())[-3:]:
                    for target in [value]:
                        try:
                            text=image.string(target)
                            if len(text)<180: annotations.append(text)
                        except Exception: pass
                        try:
                            text=image.string(image.pointer(target+16))
                            if len(text)<180: annotations.append(text)
                        except Exception: pass
                out.append({"address":hex(ins.address),"instruction":ins.mnemonic+" "+ins.op_str,"strings":sorted(set(annotations))})
                if ins.mnemonic in ("bl","blr"): regs={k:v for k,v in regs.items() if ins.reg_name(k).startswith("x") and int(ins.reg_name(k)[1:])>=19}
            callees=[]
            for ins in decoder.disasm(data[offset:offset+size],address):
                if ins.mnemonic!="bl" or not ins.operands or ins.operands[0].type!=ARM64_OP_IMM: continue
                target=ins.operands[0].imm
                if not 0x10fa00000<=target<0x10fc00000: continue
                try: off,_=image.location(target,16)
                except Exception: continue
                tracked={}; names=[]
                for part in decoder.disasm(data[off:off+16],target):
                    ps=part.operands
                    if part.mnemonic=="adrp" and len(ps)==2: tracked[ps[0].reg]=ps[1].imm
                    elif part.mnemonic=="ldr" and len(ps)==2 and ps[1].type==ARM64_OP_MEM and ps[1].mem.base in tracked:
                        try:
                            v=image.pointer(tracked[ps[1].mem.base]+ps[1].mem.disp)
                            names.append(image.string(v))
                        except Exception: pass
                if names: callees.append({"target":hex(target),"selectors":names})
            print("QQ_DEVICE_CALLEES "+json.dumps({"method":label,"callees":callees}),flush=True)
            print("QQ_DEVICE_DISASSEMBLY "+json.dumps({"method":label,"instructions":out}),flush=True)
