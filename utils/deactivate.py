import os

def kill_procces():
    os.system('pkill -f main.py')

if __name__ == '__main__':
    kill_procces()
