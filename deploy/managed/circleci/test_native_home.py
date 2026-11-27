"""CI macOS only: prove Foundation reads the caller's isolated saved account cache."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest
from task_context import minimal_env

class NativeHomeTests(unittest.TestCase):
    @unittest.skipUnless(platform.system()=="Darwin","actual macOS Foundation required")
    def test_foundation_uses_private_home_for_saved_cache(self):
        swift=shutil.which("swift")
        self.assertIsNotNone(swift)
        with tempfile.TemporaryDirectory(prefix="native-home-contract-") as folder:
            root=Path(folder);root.chmod(0o700)
            home=root/"isolated-home";home.mkdir(mode=0o700)
            cache=home/".ipatool"/("a"*32)
            cache.parent.mkdir(mode=0o700);cache.mkdir(mode=0o700)
            account=cache/"account.json";account.write_text('{"synthetic":true}');account.chmod(0o600)
            env=minimal_env(dict(os.environ,CFFIXED_USER_HOME="must-not-inherit"),home)
            self.assertEqual(env["CFFIXED_USER_HOME"],str(home))
            program=r'''
import Foundation
let actual = FileManager.default.homeDirectoryForCurrentUser.standardizedFileURL
let expected = URL(fileURLWithPath: ProcessInfo.processInfo.environment["HOME"]!).standardizedFileURL
guard actual.path == expected.path else { exit(2) }
let cache = actual.appendingPathComponent(".ipatool/" + String(repeating:"a",count:32) + "/account.json")
guard let data = try? Data(contentsOf: cache),
      let object = try? JSONSerialization.jsonObject(with:data) as? [String:Bool],
      object == ["synthetic":true] else { exit(3) }
print("native_private_cache_verified")
'''
            result=subprocess.run([swift,"-e",program],cwd=root,env=env,stdin=subprocess.DEVNULL,
                capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,"Foundation private-home contract failed")
            self.assertEqual(result.stdout.strip(),"native_private_cache_verified")
        self.assertFalse(home.exists())

if __name__=="__main__":unittest.main()
