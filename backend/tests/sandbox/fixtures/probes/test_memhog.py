def test_memory_hog():
    hog = []
    while True:
        hog.append(bytearray(50 * 1024 * 1024))
