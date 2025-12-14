import elevenlabs, pkgutil, os
print("elevenlabs __file__ ->", getattr(elevenlabs,'__file__','MISSING'))
print()
print("TOP-LEVEL NAMES:")
print([n for n in dir(elevenlabs) if not n.startswith('_')][:200])
print()
print("SUBMODULES:")
try:
    for m in pkgutil.iter_modules(elevenlabs.__path__):
        print(" -", m.name)
except Exception as e:
    print("pkgutil.iter_modules() failed ->", repr(e))
print()
print("CURRENT FOLDER CONTENTS:")
for p in os.listdir("."):
    print(" -", p)
