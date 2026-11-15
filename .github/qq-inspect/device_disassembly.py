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
            print("QQ_DEVICE_DISASSEMBLY "+json.dumps({"method":label,"instructions":out}),flush=True)
