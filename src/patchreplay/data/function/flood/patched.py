import os
while True:
    os.write(1, b'x' * 4096)
