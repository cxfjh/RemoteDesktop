import cv2
import socket
import pyautogui
from mss import mss
from numpy import array
from pickle import dumps, loads
from struct import pack, unpack, calcsize
from asyncio import get_event_loop, run, sleep, gather, Queue


# 全局变量
serverIp = None  # 服务器IP地址
serverPort = None  # 端口号
pyautogui.FAILSAFE = False  # 禁用 PyAutoGUI 的 fail-safe 机制
fps = 20  # 设置帧率
screenWidth, screenHeight = pyautogui.size()  # 获取屏幕分辨率
captureRegion = {"top": 0, "left": 0, "width": screenWidth, "height": screenHeight}  # 捕获区域
jpegQuality = 80  # 图像质量的压缩参数
clientSocket = None  # 客户端socket对象
imageQueue = Queue(maxsize=1)  # 创建队列对象
sct = mss()  # 创建mss对象


# 连接服务端
async def connectServer():
    global clientSocket
    while True:
        try:
            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # 创建socket对象
            clientSocket.connect((serverIp, serverPort))
            print("连接成功")
            break
        except Exception as e: print(f"连接失败: {e}"); await sleep(3)  # 重试连接


# 捕获屏幕并放入队列
async def captureScreen():
    while True:
        try:
            # 捕获屏幕
            screenshot = sct.grab(captureRegion)
            imgNp = array(screenshot)
            _, encodedImage = cv2.imencode('.jpg', imgNp, [int(cv2.IMWRITE_JPEG_QUALITY), jpegQuality])
            if not _: print("图像编码失败"); continue  # 跳过本帧，避免程序崩溃

            # 将图像数据转换为字节流并放入队列
            data = dumps(encodedImage)
            await imageQueue.put(data)
            await sleep(1 / fps)
        except Exception as e: print(f"捕获屏幕时发生错误: {e}"); await sleep(1)


# 发送图像函数
async def sendImageAsync():
    while True:
        try:
            data = await imageQueue.get()  # 从队列中取出图像数据
            messageSize = pack("L", len(data))  # 发送数据的长度
            clientSocket.settimeout(1)  # 设置发送数据超时时间
            clientSocket.sendall(messageSize + data)  # 发送图像数据
            clientSocket.settimeout(None)  # 取消发送数据超时时间
        except (ConnectionAbortedError, ConnectionResetError) as e: print(f"发送图像时发生错误: {e}"); await connectServer()  # 重新连接服务器
        except Exception as e: print(f"发送图像时发生错误: {e}");  await sleep(1)


# 接收事件函数
async def receiveEventsAsync():
    while True:
        try:
            # 接收数据的大小
            messageSize = await get_event_loop().sock_recv(clientSocket, calcsize("L"))
            if not messageSize: await connectServer(); continue
            dataSize = unpack("L", messageSize)[0]

            # 接收事件数据
            data = b""
            while len(data) < dataSize:
                packet = await get_event_loop().sock_recv(clientSocket, 4096)
                if not packet: await connectServer(); break # 重新连接服务器
                data += packet

            # 解码事件数据
            event = loads(data)
            eventType = event["type"]
            eventData = event["data"]

            # 处理事件
            if eventType == "mouse_click": x, y = eventData["x"], eventData["y"]; pyautogui.click(x, y)  # 鼠标点击
            elif eventType == "mouse_double_click": x, y = eventData["x"], eventData["y"]; pyautogui.doubleClick(x, y)  # 鼠标双击
            elif eventType == "mouse_right_click": x, y = eventData["x"], eventData["y"]; pyautogui.click(x, y, button='right')  # 鼠标右键点击
            elif eventType == "key_press": key = eventData["key"]; pyautogui.press(key)  # 按键按下
        except (ConnectionAbortedError, ConnectionResetError) as e: print(f"接收事件时发生错误: {e}"); await connectServer()  # 重新连接服务器
        except Exception as e: print(f"接收事件时发生错误: {e}"); await sleep(1)


# 定义任务函数
async def startCapture(): await captureScreen()  # 启动捕获屏幕任务
async def startSending(): await sendImageAsync()  # 启动发送图像任务
async def startReceiving(): await receiveEventsAsync()  # 启动接收事件任务


# 启动捕获和发送任务
async def main():
    await connectServer()
    await gather(startCapture(), startSending(), startReceiving())


# 启动事件循环并运行
def runClient():
    global serverIp, serverPort
    serverIp = input("请输入服务器IP地址: ")
    serverPort = int(input("请输入服务器端口号: "))

    try: run(main())
    except KeyboardInterrupt:
        print("程序被用户中断")
        if clientSocket: clientSocket.close()
        print("连接关闭")
