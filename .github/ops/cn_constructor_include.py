"""Expose the reviewed original static constructor for a public diagnostic only."""
from pathlib import Path
ENTRY='int main(int argc,const char **argv) { @autoreleasepool {'
def constructor(text):
    if text.count(ENTRY)!=1:raise ValueError('native_entry_contract')
    body=text.split(ENTRY)[0]
    if body.count('static NSMutableURLRequest *PreparedCommerceSession(')!=1:raise ValueError('native_constructor_contract')
    return body
if __name__=='__main__':Path('.github/ops/CNEnrollmentConstructor.inc').write_text(constructor(Path('tools/NativeMachineEnrollment.m').read_text()))
