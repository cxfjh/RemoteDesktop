from utils.client import runClient
from utils.server import startServer


if __name__ == '__main__':
    while True:
        menu = input("1. 启动服务器\n2. 启动客户端\n请选择功能：")
        print()
        if menu == "1": startServer(); break
        elif menu == "2": runClient(); break
    