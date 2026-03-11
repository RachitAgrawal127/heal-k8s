import time

def leak_memory():
    leaked = []
    print("Leaky app started. Allocating memory every second...")
    
    while True:
        # Allocate 5MB every second and never release it
        chunk = " " * (5 * 1024 * 1024)  # 5MB string
        leaked.append(chunk)  # keeping reference = GC can never free it
        
        total_mb = len(leaked) * 5
        print(f"Total leaked: {total_mb} MB")
        time.sleep(1)

if __name__ == "__main__":
    leak_memory()