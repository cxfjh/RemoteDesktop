import cv2
import socket
from threading import Thread
from PIL import Image, ImageTk
from pickle import dumps, loads
from asyncio import run, to_thread, wait_for, TimeoutError
from tkinter import Tk, Label, BOTH
from struct import pack, unpack


# 全局变量声明
root = None  # GUI窗口
label = None  # 图像标签
latestFrame = None  # 最新图像帧
eventSocket = None  # 事件套接字
imgWidth = 0  # 图像宽度
imgHeight = 0  # 图像高度
serverIp = socket.gethostbyname(socket.gethostname())  # 获取本地IP地址
serverPort = 4399  # 服务器端口号


# 图像更新函数，主线程调用
def updateImage():
    global latestFrame, imgWidth, imgHeight  # 添加全局变量声明
    if latestFrame is not None:
        # 获取窗口当前的大小
        windowWidth = root.winfo_width()
        windowHeight = root.winfo_height()
        imgHeight, imgWidth, _ = latestFrame.shape
        aspectRatio = imgWidth / imgHeight

        # 计算新的图像大小，保持比例
        if windowWidth / windowHeight > aspectRatio:
            newHeight = windowHeight
            newWidth = int(newHeight * aspectRatio)
        else:
            newWidth = windowWidth
            newHeight = int(newWidth / aspectRatio)

        # 使用OpenCV缩放图像，以适应窗口大小
        imgResized = cv2.resize(latestFrame, (newWidth, newHeight), interpolation=cv2.INTER_LINEAR)
        imgPil = Image.fromarray(imgResized)
        imgTk = ImageTk.PhotoImage(imgPil)
        label.config(image=imgTk)  # 更新图像
        label.image = imgTk  # 保存引用，防止图像被垃圾回收

    # 每50ms更新一次
    root.after(50, updateImage)


# 鼠标事件处理函数
def onMouseEvent(event, eventType):
    global eventSocket, imgWidth, imgHeight
    if eventSocket is not None:
        x = int(event.x * imgWidth / label.winfo_width())
        y = int(event.y * imgHeight / label.winfo_height())
        eventData = {"x": x, "y": y}
        eventPacket = dumps({"type": eventType, "data": eventData})
        eventSocket.sendall(pack("L", len(eventPacket)) + eventPacket)


# 键盘按键事件处理函数
def onKeyPress(event):
    global eventSocket
    if eventSocket is not None:
        key = event.keysym
        eventType = "key_press"
        eventData = {"key": key}
        eventPacket = dumps({"type": eventType, "data": eventData})
        eventSocket.sendall(pack("L", len(eventPacket)) + eventPacket)


# 异步IO函数，用于接收图像数据
async def receiveImageAsync(clientSocket):
    global eventSocket, latestFrame
    eventSocket = clientSocket
    try:
        while True:
            try:
                # 接收数据大小
                dataSize = unpack("L", await wait_for(to_thread(clientSocket.recv, 4), timeout=1))[0]
                if dataSize > 0.5 * 1024 * 1024: raise OverflowError("数据大小超过0.5MB")

                # 接收图像数据
                data = b""
                while len(data) < dataSize:
                    packet = await wait_for(to_thread(clientSocket.recv, 4096), timeout=1)  # 设置超时时间为2秒
                    if not packet: break
                    data += packet

                # 解码图像数据
                encodedImage = loads(data)
                img = cv2.imdecode(encodedImage, cv2.IMREAD_COLOR)
                imgRgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # 转换为RGB格式（Tkinter使用的格式）
                latestFrame = imgRgb  # 将图像数据放入全局变量
            except TimeoutError: print("接收图像超时，跳过该图像"); continue
            except Exception as e: print(f"接收图像时发生错误: {e}"); break
    except Exception as e: print(f"接收图像时发生错误: {e}")


# 异步IO函数，用于启动服务器并接收图像数据
async def startAsyncioServer():
    while True:  # 重连机制
        try:
            # 创建 TCP socket 并绑定
            serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serverSocket.bind((serverIp, serverPort))
            serverSocket.listen(1)
            print(f"服务器正在监听 {serverIp}:{serverPort}...")

            # 等待客户端连接
            clientSocket, clientAddress = serverSocket.accept()
            print(f"客户端 {clientAddress} 已连接")
            await receiveImageAsync(clientSocket) # 使用异步IO处理图像接收
            clientSocket.close()  # 关闭连接
        except Exception as e: print(f"等待客户端重新连接... {e}"); continue
        finally: serverSocket.close()  # 确保服务器套接字关闭


# 启动异步IO事件循环
async def runs(): await startAsyncioServer()


# 启动服务器
def startServer():
    # 创建GUI窗口并设置初始大小
    global root, label
    root = Tk()
    root.title("实时屏幕显示")
    root.geometry("1280x720")
    label = Label(root)
    label.pack(fill=BOTH, expand=True)


    # 使用线程来运行异步IO事件循环
    asyncioThread = Thread(target=run, args=(runs(),), daemon=True)
    asyncioThread.start()


    # 绑定鼠标事件
    mouseEventTypes = {
        "<Button-1>": "mouse_click",
        "<Double-1>": "mouse_double_click",
        "<Button-3>": "mouse_right_click"
    }


    # 绑定鼠标事件
    for event, eventType in mouseEventTypes.items(): label.bind(event, lambda event, eventType=eventType: onMouseEvent(event, eventType))
    root.bind("<Key>", onKeyPress) # 绑定键盘按键事件


    # 启动GUI更新函数
    updateImage() # 启动GUI更新函数
    root.mainloop() # 启动Tkinter的主事件循环
