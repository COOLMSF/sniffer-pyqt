# -*- coding: utf8 -*-

from PyQt5 import QtCore,QtGui,QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from Ui_main import *

# import alarm
from scapy.all import *
import os
import time
import multiprocessing
from scapy.layers import http
import numpy as np
import matplotlib.pyplot as plt

import argparse
import logging
import scapy
from re import findall
from scapy.all import *
from base64 import b64decode
from datetime import datetime

# Static Global Vars
NULL_FLAG = 0b00000000
FIN_FLAG = 0b00000001
XMAS_FLAG = 0b00101001
# HTTP_AUTH_KEYWD = "Authorization: Basic"
# NIKTO_KEYWORDS = ["Nikto", "nikto", "NIKTO"]
# SHOCK_KEYWORDS = ["() { :; };", "(){:;};", "() { :;};", "() { : ; } ;", "() {:; };"]
# USER_KEYWORDS = ["mac", "log", "login", "wpname", "ahd_username", "unickname", "nickname", "user", "user_name", "alias",
#                  "pseudo", "email", "username", "_username", "userid", "form_loginname", "loginname", "login_id",
#                  "loginid", "session_key", "sessionkey", "pop_login", " uid", " id", "user_id", "screenname", "uname",
#                  "ulogin", "acctname", "account", "member", "mailaddress", "membername", "login_username",
#                  "login_email", "loginusername", "loginemail", "uin", "sign-in"]
# PASS_KEYWORDS = ["pass", "ahd_password", "pass password", "_password passwd", "session_password", "sessionpassword",
#                  "login_password", "loginpassword", "form_pw", "pw", "userpassword", "pwd", "upassword",
#                  "login_password", "passwort", "passwrd", "wppassword", "upasswd"]
PROTOCOLS = ["HOPOPT", "ICMP", "IGMP", "GGP", "IPv4", "ST", "TCP", "CBT", "EGP", "IGP", "BBN-RCC-MON", "NVP-II", "PUP",
            "ARGUS", "EMCON", "XNET", "CHAOS", ]
HTTP_AUTH_KEYWD = list()
NIKTO_KEYWORDS = list()
SHOCK_KEYWORDS = list()
USER_KEYWORDS = list()
PASS_KEYWORDS = list()


def kmp(text, pattern):
    n = len(text)
    m = len(pattern)
    if m == 0:
        return 0
    fail = [0] * m
    j = 0
    for i in range(1, m):
        while j > 0 and pattern[j] != pattern[i]:
            j = fail[j-1]
        if pattern[j] == pattern[i]:
            j += 1
        fail[i] = j
    j = 0
    for i in range(n):
        while j > 0 and pattern[j] != text[i]:
            j = fail[j-1]
        if pattern[j] == text[i]:
            j += 1
        if j == m:
            return i - m + 1
    return -1

class Packet:
    srcIP = ''
    protocol = ''
    rawData = ''
    flags = 0x00

    def __init__(self, in_packet):
        self.srcIP = str(in_packet[IP].src)
        self.protocol = int(in_packet.proto)
        self.rawData = str(in_packet)
        self.flags = in_packet[TCP].flags

def string_entropy(s):
    freqs = {}
    for c in s:
        if c in freqs:
            freqs[c] += 1
        else:
            freqs[c] = 1
    entropy = 0
    for freq in freqs.values():
        p = float(freq) / len(s)
        entropy -= p * math.log(p, 2)
    return entropy

# print_alert()
#
# Prints an alert pertinent to what was picked up on the alarm.
def print_alert(scan_type, src, proto, payload):
    global ALERT_COUNTER

    ALERT_COUNTER += 1
    if payload == "":
        print("ALERT #%d: %s is detected from %s (%s)!" % (ALERT_COUNTER, scan_type, src, PROTOCOLS[proto]))
        logging.info("ALERT #%d: %s is detected from %s (%s)!" % (ALERT_COUNTER, scan_type, src, PROTOCOLS[proto]
                                                                   ))
    else:
        print("ALERT #%d: %s from %s (%s) !" % (ALERT_COUNTER, scan_type, src, PROTOCOLS[proto] ))
        logging.info("ALERT #%d: %s from %s (%s)!" % (ALERT_COUNTER, scan_type, src, PROTOCOLS[proto]))


# scan_check()
#
# Checks given Packet object for traces of a NULL, FIN, or XMAS nmap stealthy scan. Does this by checking what flags are
# set in the TCP layer, which will allow for the detection of a stealthy scan. Calls on print_alert() if packet seems to
# be from an nmap stealth scan.
def scan_check(in_packet):
    global ALERT_COUNTER

    if in_packet.flags == NULL_FLAG:  # NULL SCAf N
        print("NULL scan detected from " + in_packet.srcIP)
        # print_alert("NULL scan", in_packet.srcIP, in_packet.protocol, "aaa")
        # print("NULL scan"+ in_packet.srcIP+ in_packet.protocol)
        return in_packet.rawData
    elif in_packet.flags == FIN_FLAG:  # FIN SCAN
        # print_alert("FIN scan", in_packet.srcIP, in_packet.protocol, "aaa")
        print("FIN scan detected")
        return in_packet.rawData
    elif in_packet.flags == XMAS_FLAG:  # XMAS SCAN
        # print_alert("XMAS scan", in_packet.srcIP, in_packet.protocol, "aaa")
        print("XMAS scan detected")
        return in_packet.rawData


# nikto_check()
#
# Checks given Packet object for traces of a Nikto scan. Does this by checking for references to keywords associated
# with the Nikto program (NIKTO_KEYWORDS) to identify a Nikto scan.
def nikto_check(in_packet):
    global ALERT_COUNTER

    for keyword in NIKTO_KEYWORDS:
        if keyword in in_packet.rawData:
            print_alert("Nikto scan", in_packet.srcIP, in_packet.protocol, "")


# get_shock_script()
#
# Helper function to obtain the command that was attempted to be run in a Shellshock attack. Used by shellshock_check().
def get_shock_script(packet_data):
    shellshock_line = ""  # Return empty string if not found

    data = packet_data.splitlines()
    # for line in data:
    #     for keyword in SHOCK_KEYWORDS:
    #         if keyword in line:
    #             shellshock_line = line
    #             break
    for line in data:
        for keyword in SHOCK_KEYWORDS:
            if kmp(line, keyword) != -1:
                shellshock_line = line
                break

    return shellshock_line


# shellshock_check()
#
# Checks a packet for traces of a Shellshock attack. Does this by looking for shellshock entry queries.
def shellshock_check(in_packet):
    global ALERT_COUNTER

    for keyword in SHOCK_KEYWORDS:
        if kmp(str(in_packet.rawData), keyword) != -1:
            print_alert("Shellshock attack", in_packet.srcIP, in_packet.protocol,
                        get_shock_script(in_packet.rawData))
            return in_packet.rawData


# get_username()
#
# Returns the username that was found in the raw data of a network packet. Helper function to find_user_pass().
def get_username(raw_data):
    words = str(raw_data).split()

    for i in range(len(words)):
        for keyword in USER_KEYWORDS:
            # if keyword in words[i].lower():
            if kmp(words[i], keyword) != -1:
                # coolder modified
                # return words[i + 1]
                return words[i]

def get_txt_filename(raw_data):
    
    lines = raw_data.rawData.splitlines()
    
    # Define the regular expression pattern to match txt file names
    pattern = r"\.txt$"
    
    for line in lines:
        if re.search(pattern, line):
            return line
    


def get_pic_filename(raw_data):
    
    # Define the regular expression pattern to match txt file names
    pattern = r"\.txt$"
    
    lines = raw_data.rawData.splitlines()
    for line in lines:
        if re.search(pattern, line):
            return line


# getPassword()
#
# Returns the password that was found in the raw data of a network packet. Helper function to find_user_pass().
def get_password(raw_data):
    words = str(raw_data).split()

    for i in range(len(words)):
        for keyword in PASS_KEYWORDS:
            if keyword in words[i].lower():
                # return words[i + 1]
                return words[i]


# find_user_pass()
#
# Helper function to user_pass_check, where after it is determined that a username and password was sent in the clear,
# it will call on this function in order to find the username and password combination (even if split between packets)
# and calls on the print_alert() function.
def find_user_pass(raw_packet, parsed_packet):
    global ALERT_COUNTER, tempUserPass
    raw_data = parsed_packet.getlayer(Raw)  # Get only the Raw layer of the raw_packet

    for keyword in USER_KEYWORDS:
        if keyword in str(raw_data).lower():
            username = get_username(raw_data)
            tempUserPass = username

    for keyword in PASS_KEYWORDS:
        if keyword in str(raw_data).lower():
            password = get_password(raw_data)
            user_pass = tempUserPass + ":" + password

            if not check_if_printable(user_pass):
                continue

            tempUserPass = ""
            print_alert("Username and password sent in the clear", raw_packet.srcIP, raw_packet.protocol, user_pass)
            tempUserPass = ""


# check_if_printable()
#
# In order to try and decrease false positives for credentials sent in-the-clear, check if the username and password are
# ASCII characters and non-control characters
def check_if_printable(username_password):
    try:
        for character in username_password:
            # Check that credentials only use extended-ASCII and non-control characters
            if ord(character) > 255 or ord(character) < 32:
                return False
    # Unable to get char value
    except TypeError:
        return False

    return True


# user_pass_check()
#
# Checks whether or not credentials have been sent in-the-clear. If it believes
# there are credentials in the packet, sends to find_user_pass() to find and
# report them.
def user_pass_check(raw_packet):
    global ALERT_COUNTER, tempUserPass
    
    words = str(raw_packet).split()

    # print("user pass fun called")
    data = raw_packet.rawData.splitlines()
    # print(data)
    # print(packet[Raw].load.decode('utf-8','ignore'))
    for line in data:
        for user_keyword in USER_KEYWORDS:
            if user_keyword in line:
                return line

        for pass_keyword in PASS_KEYWORDS:
            if pass_keyword in line:
                return line
        

# credit_card_check()
#
# Checks whether or not credit card numbers have been sent in-the-clear. If it believes
# there are credentials in the packet,
def credit_card_check(in_packet):
    data = in_packet.rawData.splitlines()

    for line in data:

        visa_num = findall('4[0-9]{12}(?:[0-9]{3})?', str(line))
        mastercard_num = findall('(?:5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}', str(line))
        diners_club_num = findall('3(?:0[0-5]|[68][0-9])[0-9]{11}', str(line))
        discover_num = findall('6(?:011|5[0-9]{2})[0-9]{12}', str(line))
        jcb_num = findall('(?:2131|1800|35\d{3})\d{11}', str(line))
        american_express_num = findall('3[47][0-9]{13}', str(line))
        bcglobal_num = findall('^(6541|6556)[0-9]{12}', str(line))
        korean_local_num = findall('^9[0-9]{15}', str(line))
        laser_card_num = findall('^(6304|6706|6709|6771)[0-9]{12,15}', str(line))
        maestro_num = findall('^(5018|5020|5038|6304|6759|6761|6763)[0-9]{8,15}', str(line))
        union_pay_num = findall('^(62[0-9]{14,17})', str(line))

        if visa_num or mastercard_num or diners_club_num:
            return line



# sniff_packet()
#
# Sniffs a given packet. Will call on four functions to protect against: nmap
# stealthy scans, Nikto scans, Shellshock attacks, and credentials sent
# in-the-clear.
def sniff_packet(in_packet):
    temp_packet = Packet(in_packet)

    scan_check(temp_packet)
    nikto_check(temp_packet)
    shellshock_check(temp_packet)
    user_pass_check(temp_packet)
    credit_card_check(temp_packet)


def packet_callback(in_packet):
    try:
        sniff_packet(in_packet)
    except IndexError:
        pass
    ## except StandardError:
    ##     pass


isDDOSCheckBoxChecked = False
isPlainInfoCheckBoxChecked = False
isUserCheckBoxChecked = False
isCreditCheckBoxChecked = False
isScanAttackCheckBoxChecked = False
isForkBoomCheckBoxChecked = False
isTxtFilenameCheckBoxChecked = False
isPicFilenameCheckBoxChecked = False


def load_rules(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
        for line in lines:
            rule = line.strip()
            if "nickto" in filename or "NICKTO" in filename:
                NIKTO_KEYWORDS.append(rule)
            if "http" in filename or "HTTP" in filename:
                HTTP_AUTH_KEYWD.append(rule)
            if "shock" in filename or "SHOCK" in filename:
                NIKTO_KEYWORDS.append(rule)
            if "user" in filename or "USER" in filename:
                USER_KEYWORDS.append(rule)
            if "pass" in filename or "PASS" in filename:
                PASS_KEYWORDS.append(rule)


class SnifferMainWindow(Ui_MainWindow,QtWidgets.QMainWindow):
    filter = ""   #捕获过滤
    iface = ""   #网卡
    packetList = []
    q = multiprocessing.Queue()
    def __init(self):
        super(SnifferMainWindow,self).__init__()
        for rule_file in os.listdir("rules"):
            load_rules(rule_file)

    def setupUi(self, MainWindow):
        super(SnifferMainWindow, self).setupUi(MainWindow)

        # stretch
        self.tableWidget.horizontalHeader().setStretchLastSection(True)
        self.tableWidgetAttackInfo.horizontalHeader().setStretchLastSection(True)
        
        self.tableWidget.insertColumn(7)
        self.tableWidget.setColumnHidden(7,True)#将最后一列隐藏
        self.tableWidget.horizontalHeader().setSectionsClickable(False) #可以禁止点击表头的列
        #self.tableWidget.horizontalHeader().setStyleSheet('QHeaderView::section{background:green}')#设置表头的背景色为绿色
        self.tableWidget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows) #设置 不可选择单个单元格，只可选择一行。
        self.tableWidget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers) #设置表格不可更改
        self.tableWidget.verticalHeader().setVisible(False) #去掉垂直表头
        self.tableWidget.setColumnWidth(0,60)
        self.tableWidget.setColumnWidth(2,150)
        self.tableWidget.setColumnWidth(3,150)
        self.tableWidget.setColumnWidth(4,60)
        self.tableWidget.setColumnWidth(5,60)
        self.tableWidget.setColumnWidth(6,600)

        self.treeWidget.setHeaderHidden(True) #去掉表头
        self.treeWidget.setColumnCount(1)

        MainWindow.setWindowIcon(QtGui.QIcon('./img/title'))


    #设置槽函数
    def setSlot(self):
        self.tableWidget.itemClicked.connect(self.clickInfo)  #左键点击
        # 必须将ContextMenuPolicy设置为Qt.CustomContextMenu
        # 否则无法使用customContextMenuRequested信号
        self.tableWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableWidget.customContextMenuRequested.connect(self.showContextMenu)

        # 创建QMenu
        self.contextMenu = QMenu(self.tableWidget)
        self.pdfdumpActionA = self.contextMenu.addAction(u'保存为pdf')
        # 将动作与处理函数相关联
        # 这里为了简单，将所有action与同一个处理函数相关联，
        # 当然也可以将他们分别与不同函数关联，实现不同的功能
        self.pdfdumpActionA.triggered.connect(self.pdfdump)

        global count
        count = 0
        global display
        display = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.statistics)
        #开启统计
        self.timer.start(1000)

        self.comboBoxIface = QComboBox()
        self.toolBar.addWidget(self.comboBoxIface)
        self.LookupIface()

        startAction = QAction(QIcon('./img/start'),'&开始捕获(Ctrl+E)',self)
        startAction.setShortcut('Ctrl+E')
        startAction.triggered.connect(self.Start)
        self.toolBar.addAction(startAction)

        stopAction = QAction(QIcon('./img/stop'),'&停止捕获(Ctrl+Q)',self)
        stopAction.setShortcut('Ctrl+Q')
        stopAction.triggered.connect(self.Stop)
        self.toolBar.addAction(stopAction)

        preFilterAction = QAction(QIcon('./img/PreFilter'),'&捕获过滤(Ctrl+T)',self)
        preFilterAction.setShortcut('Ctrl+T')
        preFilterAction.triggered.connect(self.PreFilter)
        self.toolBar.addAction(preFilterAction)

        postFilterAction = QAction(QIcon('./img/PostFilter'),'&显示过滤(Ctrl+F)',self)
        postFilterAction.setShortcut('Ctrl+F')
        postFilterAction.triggered.connect(self.PostFilter)
        self.toolBar.addAction(postFilterAction)

        saveAction = QAction(QIcon('./img/save'),'&保存(Ctrl+S)',self)
        saveAction.setShortcut('Ctrl+S')
        saveAction.triggered.connect(self.savePackets)
        self.toolBar.addAction(saveAction)

        statisticsAction = QAction(QIcon('./img/statistics'),'&统计数据(Ctrl+G)',self)
        statisticsAction.setShortcut('Ctrl+G')
        statisticsAction.triggered.connect(self.statisticsMenu)
        self.toolBar.addAction(statisticsAction)

        aboutAction = QAction(QIcon('./img/about'),'&关于(Ctrl+B)',self)
        aboutAction.setShortcut('Ctrl+B')
        aboutAction.triggered.connect(self.about)
        self.toolBar.addAction(aboutAction)

        self.checkBoxDDOS.stateChanged.connect(self.choose)
        self.checkBoxCredit.stateChanged.connect(self.choose)
        self.checkBoxForkBoom.stateChanged.connect(self.choose)
        self.checkBoxScanAttack.stateChanged.connect(self.choose)
        self.checkBoxUser.stateChanged.connect(self.choose)
        self.checkBoxTxtFilename.stateChanged.connect(self.choose)
        self.checkBoxPicFilename.stateChanged.connect(self.choose)



    def choose(self):
        # QMessageBox(text="ddos checked").exec() if self.checkBoxDDOS.isChecked() else QMessageBox(text="ddos not checked").exec()
        global isDDOSCheckBoxChecked
        global isPlainInfoCheckBoxChecked
        global isUserCheckBoxChecked
        global isCreditCheckBoxChecked
        global isScanAttackCheckBoxChecked
        global isForkBoomCheckBoxChecked
        global isTxtFilenameCheckBoxChecked
        global isPicFilenameCheckBoxChecked

        if self.checkBoxDDOS.isChecked():
            isDDOSCheckBoxChecked = True
        else:
            isDDOSCheckBoxChecked = False

        if self.checkBoxForkBoom.isChecked():
            isForkBoomCheckBoxChecked = True
        else:
            isForkBoomCheckBoxChecked = False

        if self.checkBoxUser.isChecked():
            isUserCheckBoxChecked = True
        else:
            isUserCheckBoxChecked = False

        if self.checkBoxCredit.isChecked():
            isCreditCheckBoxChecked = True
        else:
            isCreditCheckBoxChecked = False


        if self.checkBoxScanAttack.isChecked():
             isScanAttackCheckBoxChecked = True
        else:
             isScanAttackCheckBoxChecked = False


        if self.checkBoxTxtFilename.isChecked():
             isTxtFilenameCheckBoxChecked = True
        else:
             isTxtFilenameCheckBoxChecked = False

        if self.checkBoxPicFilename.isChecked():
             isPicFilenameCheckBoxChecked = True
        else:
             isPicFilenameCheckBoxChecked = False

    def about(self):
        msg = QMessageBox()
        msg.setWindowTitle("关于我")
        msg.setText("作者: xxxxx\nEmail:xxxx.com")
        msg.exec()

    #统计数据菜单
    def statisticsMenu(self):
        list = ["网络层", "传输层"]

         #第三个参数可选 有一般显示 （QLineEdit.Normal）、密碼显示（ QLineEdit. Password）与不回应文字输入（ QLineEdit. NoEcho）
        #stringNum,ok3 = QInputDialog.getText(self, "标题","姓名:",QLineEdit.Normal, "王尼玛")
         #1为默认选中选项目，True/False  列表框是否可编辑。
        item, ok = QInputDialog.getItem(self, "选项","统计类别", list, 1, False)
        if ok:
            if item =="网络层"  :
                ip = 0
                arp = 0
                count = 0
                for pkt in self.packetList:
                    if pkt.type == 0x800:
                        ip += 1
                        count += 1
                    elif pkt.type == 0x806:
                        arp += 1
                        count += 1
                ipPercent = '{:.1f}'.format(ip/count)
                arpPercent = '{:.1f}'.format(arp/count)
                plt.rcParams['font.sans-serif']=['SimHei'] #用来正常显示中文标签
                plt.rcParams['axes.unicode_minus']=False #用来正常显示负号
                labels = 'IP(%s)' % ip ,'ARP(%s)' % arp
                fracs = [ipPercent,arpPercent]
                explode = [0,0]#比例,与上面要一一对应
                plt.axes(aspect=1)#此处的aspect=1表示正圆，取不同的值，表示的圆形状不同
                plt.pie(x=fracs, labels=labels, explode=explode, autopct='%3.1f %%',
                    shadow=True, labeldistance=1.1, startangle=90, pctdistance=0.6
                )
                '''
                labeldistance，文本的位置离远点有多远，1.1指1.1倍半径的位置
                autopct，圆里面的文本格式，%3.1f%%表示小数有三位，整数有一位的浮点数
                shadow，饼是否有阴影
                startangle，起始角度，0，表示从0开始逆时针转，为第一块。一般选择从90度开始比较好看
                pctdistance，百分比的text离圆心的距离
                patches, l_texts, p_texts，为了得到饼图的返回值，p_texts饼图内部文本的，l_texts饼图外label的文本
                '''
                plt.title("网络层统计(捕获：%s)" %count)
                plt.show()
            elif item =="传输层":
                tcp = 0
                udp = 0
                icmp = 0
                igmp = 0
                count = 0
                for pkt in self.packetList:
                    if pkt.haslayer('IP') and pkt[IP].proto == 6:
                        tcp += 1
                        count += 1
                    elif pkt.haslayer('IP') and pkt[IP].proto == 17:
                        udp += 1
                        count += 1
                    elif pkt.haslayer('IP') and pkt[IP].proto == 1:
                        icmp += 1
                        count += 1
                    elif pkt.haslayer('IP') and pkt[IP].proto == 2:
                        igmp += 1
                        count += 1
                tcpPercent = '{:.1f}'.format(tcp/count)
                udpPercent = '{:.1f}'.format(udp/count)
                icmpPercent = '{:.1f}'.format(icmp/count)
                igmpPercent = '{:.1f}'.format(igmp/count)
                plt.rcParams['font.sans-serif']=['SimHei'] #用来正常显示中文标签
                plt.rcParams['axes.unicode_minus']=False #用来正常显示负号
                labels = 'TCP(%s)' % tcp ,'UDP(%s)' % udp ,'ICMP(%s)' % icmp ,'IGMP(%s)' % igmp
                fracs = [tcpPercent,udpPercent,icmpPercent,igmpPercent]
                explode = [0,0,0,0]#比例,与上面要一一对应
                plt.axes(aspect=1)#此处的aspect=1表示正圆，取不同的值，表示的圆形状不同
                plt.pie(x=fracs, labels=labels, explode=explode, autopct='%3.1f %%',
                    shadow=True, labeldistance=1.1, startangle=90, pctdistance=0.6
                )
                '''
                labeldistance，文本的位置离远点有多远，1.1指1.1倍半径的位置
                autopct，圆里面的文本格式，%3.1f%%表示小数有三位，整数有一位的浮点数
                shadow，饼是否有阴影
                startangle，起始角度，0，表示从0开始逆时针转，为第一块。一般选择从90度开始比较好看
                pctdistance，百分比的text离圆心的距离
                patches, l_texts, p_texts，为了得到饼图的返回值，p_texts饼图内部文本的，l_texts饼图外label的文本
                '''
                plt.title("传输层统计(捕获总数：%s)" % count)
                plt.show()



    #保存所有数据包
    def savePackets(self):
        path, filetype = QtWidgets.QFileDialog.getSaveFileName(None,
                                    "选择保存路径",
                                    "./",
                                    "pcap文件(*.cap);;全部(*)")
        if path == "":
            return
        if os.path.exists(os.path.dirname(path)) == False:
            QtWidgets.QMessageBox.critical(None,"错误","路径不存在")
            return
        packets = scapy.plist.PacketList(self.packetList)
        wrpcap(path,packets)
        QtWidgets.QMessageBox.information(None,"成功","保存成功")

    #右键点击显示菜单
    def showContextMenu(self,pos):
        '''
        右键点击时调用的函数
        '''
        # 菜单显示前，将它移动到鼠标点击的位置
        # self.contextMenu.move(self.pos() + pos)
        self.contextMenu.exec_(QCursor.pos())
    #将数据包保存为pdf
    def pdfdump(self):
        '''
        菜单中的具体action调用的函数
        '''
        row = self.tableWidget.currentRow()     #获取当前行数
        p = self.tableWidget.item(row,7).text()
        packet = scapy.layers.l2.Ether(p.encode('Windows-1252'))
        path, filetype = QtWidgets.QFileDialog.getSaveFileName(None,
                                    "选择保存路径",
                                    "./",
                                    "pdf文件(*.pdf);;全部(*)")
        if path == "":
            return
        if os.path.exists(os.path.dirname(path)) == False:
            QtWidgets.QMessageBox.critical(None,"错误","路径不存在")
            return
        self.pdfdumpThread = pdfdumpThread(packet,path)
        self.pdfdumpThread.pdfdumpSignal.connect(self.pdfdumpFinish)
        self.pdfdumpThread.start()

    #pdfdump完成消息提示
    def pdfdumpFinish(self,info):
        if info == True:
            QtWidgets.QMessageBox.information(None,"成功","保存成功")


    #开始捕获
    def Start(self):
        global count
        count = 0
        global display
        display = 0
        self.packetList = []

        self.startTime = time.time()
        self.iface = self.comboBoxIface.currentText()

        self.tableWidget.setRowCount(0)
        self.tableWidget.removeRow(0)

        self.SnifferThread = SnifferThread(self.filter,self.iface)
        self.SnifferThread.HandleSignal.connect(self.display)
        self.SnifferThread.start()




    
    def packet_entropy(self, pkt):
        if IP in pkt:
            ip_payload = pkt[IP].payload
            entropy = 0
            if len(ip_payload) > 0:
                counts = dict()
                for b in ip_payload:
                    if b in counts:
                        counts[b] += 1
                    else:
                        counts[b] = 1
                for count in counts.values():
                    probability = count / float(len(ip_payload))
                    entropy -= probability * math.log(probability, 2)
            # print("Entropy: {:.3f}".format(entropy))
            return entropy
        
    
    # Define a function to check if a packet is encrypted based on its entropy
    def is_encrypted(self, packet):
        # Calculate the entropy of the packet's payload
        payload_entropy = string_entropy(str(packet))
        print("entropy: " + str(payload_entropy))
        # Check if the entropy value is above a certain threshold
        if payload_entropy > 7.5:
            return "True"
        # If the entropy value is below the threshold, assume the packet is not encrypted
        return "False"

    #显示捕获的数据包
    def display(self,packet):



        # if self.checkBoxDDOS.isChecked():
        #     QMessageBox("ddos checked")
        global count
        global display
        packetTime = '{:.7f}'.format(packet.time - self.startTime)
        type = packet.type

        if type == 0x800 :
            count += 1
            display = count
            row = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row)
            self.tableWidget.setItem(row,0, QtWidgets.QTableWidgetItem(str(count)))
            self.tableWidget.setItem(row,1,QtWidgets.QTableWidgetItem(str(packetTime)))
            self.tableWidget.setItem(row,2, QtWidgets.QTableWidgetItem(packet[IP].src))
            self.tableWidget.setItem(row,3, QtWidgets.QTableWidgetItem(packet[IP].dst))
            self.tableWidget.setItem(row,5, QtWidgets.QTableWidgetItem(str(len(packet))))

            data = self.is_encrypted(str(packet))
            print(data)
            self.tableWidget.setItem(row,8, QtWidgets.QTableWidgetItem(data))

            self.tableWidget.setItem(row,7, QtWidgets.QTableWidgetItem(raw(packet).decode('Windows-1252','ignore')))

            #TCP
            if packet[IP].proto == 6:


                temp_packet = Packet(packet)

                if isDDOSCheckBoxChecked:
                    a = 1
                    #print("Hll")
                    # DDOS
                if isForkBoomCheckBoxChecked:
                    data = shellshock_check(temp_packet)
                    if data is not None:
                        row = self.tableWidgetAttackInfo.rowCount()
                        self.tableWidgetAttackInfo.insertRow(row)
                        self.tableWidgetAttackInfo.setItem(row,0, QtWidgets.QTableWidgetItem(str(count)))
                        self.tableWidgetAttackInfo.setItem(row,1, QtWidgets.QTableWidgetItem(packet[IP].src))
                        self.tableWidgetAttackInfo.setItem(row,2, QtWidgets.QTableWidgetItem(packet[IP].dst))
                        self.tableWidgetAttackInfo.setItem(row,3, QtWidgets.QTableWidgetItem(str("fork boom!!!")))

                if isUserCheckBoxChecked:
                    # print(isUserCheckBoxChecked)
                    # print("Hello, user check enable")
                    data = user_pass_check(temp_packet)
                    if data is not None:
                        row = self.tableWidgetAttackInfo.rowCount()
                        self.tableWidgetAttackInfo.insertRow(row)
                        self.tableWidgetAttackInfo.setItem(row,0, QtWidgets.QTableWidgetItem(str(count)))
                        self.tableWidgetAttackInfo.setItem(row,1, QtWidgets.QTableWidgetItem(packet[IP].src))
                        self.tableWidgetAttackInfo.setItem(row,2, QtWidgets.QTableWidgetItem(packet[IP].dst))
                        self.tableWidgetAttackInfo.setItem(row,3, QtWidgets.QTableWidgetItem(str("username or passwd leak")))
                        self.tableWidgetAttackInfo.setItem(row,4, QtWidgets.QTableWidgetItem(str(data)))

                if isCreditCheckBoxChecked:
                    # print("Hello, credit check enable")
                    data = credit_card_check(temp_packet)
                    if data is not None:
                        row = self.tableWidgetAttackInfo.rowCount()
                        self.tableWidgetAttackInfo.insertRow(row)
                        self.tableWidgetAttackInfo.setItem(row,0, QtWidgets.QTableWidgetItem(str(count)))
                        self.tableWidgetAttackInfo.setItem(row,1, QtWidgets.QTableWidgetItem(packet[IP].src))
                        self.tableWidgetAttackInfo.setItem(row,2, QtWidgets.QTableWidgetItem(packet[IP].dst))
                        self.tableWidgetAttackInfo.setItem(row,3, QtWidgets.QTableWidgetItem(str("credit card leak")))
                        self.tableWidgetAttackInfo.setItem(row,4, QtWidgets.QTableWidgetItem(str(data)))

                if isScanAttackCheckBoxChecked:
                    # print("Hello, scan check enable")
                    data = scan_check(temp_packet)
                    if data is not None:
                        row = self.tableWidgetAttackInfo.rowCount()
                        self.tableWidgetAttackInfo.insertRow(row)
                        self.tableWidgetAttackInfo.setItem(row,0, QtWidgets.QTableWidgetItem(str(count)))
                        self.tableWidgetAttackInfo.setItem(row,1, QtWidgets.QTableWidgetItem(packet[IP].src))
                        self.tableWidgetAttackInfo.setItem(row,2, QtWidgets.QTableWidgetItem(packet[IP].dst))
                        self.tableWidgetAttackInfo.setItem(row,3, QtWidgets.QTableWidgetItem(str("scan check")))
                        self.tableWidgetAttackInfo.setItem(row,4, QtWidgets.QTableWidgetItem(str(data)))

                if isPicFilenameCheckBoxChecked:
                    # print("Hello, scan check enable")
                    data = get_pic_filename(temp_packet)
                    if data is not None:
                        row = self.tableWidgetAttackInfo.rowCount()
                        self.tableWidgetAttackInfo.insertRow(row)
                        self.tableWidgetAttackInfo.setItem(row,0, QtWidgets.QTableWidgetItem(str(count)))
                        self.tableWidgetAttackInfo.setItem(row,1, QtWidgets.QTableWidgetItem(packet[IP].src))
                        self.tableWidgetAttackInfo.setItem(row,2, QtWidgets.QTableWidgetItem(packet[IP].dst))
                        self.tableWidgetAttackInfo.setItem(row,3, QtWidgets.QTableWidgetItem(str("TXT file found")))
                        self.tableWidgetAttackInfo.setItem(row,4, QtWidgets.QTableWidgetItem(str(data)))
                        
                if isTxtFilenameCheckBoxChecked:
                    # print("Hello, scan check enable")
                    data = get_txt_filename(temp_packet)
                    if data is not None:
                        row = self.tableWidgetAttackInfo.rowCount()
                        self.tableWidgetAttackInfo.insertRow(row)
                        self.tableWidgetAttackInfo.setItem(row,0, QtWidgets.QTableWidgetItem(str(count)))
                        self.tableWidgetAttackInfo.setItem(row,1, QtWidgets.QTableWidgetItem(packet[IP].src))
                        self.tableWidgetAttackInfo.setItem(row,2, QtWidgets.QTableWidgetItem(packet[IP].dst))
                        self.tableWidgetAttackInfo.setItem(row,3, QtWidgets.QTableWidgetItem(str("Picture found")))
                        self.tableWidgetAttackInfo.setItem(row,4, QtWidgets.QTableWidgetItem(str(data)))
                        
                #HTTP
                if packet[TCP].dport == 80 or packet[TCP].sport == 80:
                    self.tableWidget.setItem(row,4, QtWidgets.QTableWidgetItem('HTTP'))
                    if packet.haslayer('HTTPRequest'):
                        self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('%s %s %s' % (packet.sprintf("{HTTPRequest:%HTTPRequest.Method%}").strip("'"),packet.sprintf("{HTTPRequest:%HTTPRequest.Path%}").strip("'"),packet.sprintf("{HTTPRequest:%HTTPRequest.Http-Version%}").strip("'"))))
                    elif packet.haslayer('HTTPResponse'):
                        self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Status-Line%}").strip("'")))
                    else:
                        self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem(''))
                else:
                    self.tableWidget.setItem(row,4, QtWidgets.QTableWidgetItem('TCP'))
                    if packet.haslayer('TCP'):
                        flag = ''
                        if packet[TCP].flags.A:
                            if flag == '':
                                flag += 'ACK'
                            else:
                                flag += ',ACK'
                        if packet[TCP].flags.R:
                            if flag == '':
                                flag += 'RST'
                            else:
                                flag += ',RST'
                        if packet[TCP].flags.S:
                            if flag == '':
                                flag += 'SYN'
                            else:
                                flag += ',SYN'
                        if packet[TCP].flags.F:
                            if flag == '':
                                flag += 'FIN'
                            else:
                                flag += ',FIN'
                        if packet[TCP].flags.U:
                            if flag == '':
                                flag += 'URG'
                            else:
                                flag += ',URG'
                        if packet[TCP].flags.P:
                            if flag == '':
                                flag += 'PSH'
                            else:
                                flag += ',PSH'
                        if flag == '':
                            self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('%s -> %s Seq：%s Ack：%s Win：%s' % (packet[TCP].sport,packet[TCP].dport,packet[TCP].seq,packet[TCP].ack,packet[TCP].window)))
                        else:
                            self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('%s -> %s [%s] Seq：%s Ack：%s Win：%s' % (packet[TCP].sport,packet[TCP].dport,flag,packet[TCP].seq,packet[TCP].ack,packet[TCP].window)))
            #UDP
            elif packet[IP].proto == 17:
                self.tableWidget.setItem(row,4, QtWidgets.QTableWidgetItem('UDP'))
                self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('%s -> %s 长度(len)：%s' % (packet[UDP].sport,packet[UDP].dport,packet[UDP].len)))
            #ICMP
            elif packet[IP].proto == 1:
                self.tableWidget.setItem(row,4, QtWidgets.QTableWidgetItem('ICMP'))
                if packet.haslayer('ICMP'):
                    if packet[ICMP].type == 8:
                        self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('Echo (ping) request id：%s seq：%s' % (packet[ICMP].id,packet[ICMP].seq)))
                    elif packet[ICMP].type == 0:
                        self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('Echo (ping) reply id：%s seq：%s' % (packet[ICMP].id,packet[ICMP].seq)))
                    else:
                        self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('type：%s id：%s seq：%s' % (packet[ICMP].type,packet[ICMP].id,packet[ICMP].seq)))
            #IGMP
            elif packet[IP].proto == 2:
                self.tableWidget.setItem(row,4, QtWidgets.QTableWidgetItem('IGMP'))
                self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem(''))
            #其他协议
            else:
                self.tableWidget.setItem(row,4, QtWidgets.QTableWidgetItem(str(packet[IP].proto)))

            #着色分析
            self.colorItem(row,packet)

            #加入packetList中
            self.packetList.append(packet)
        #ARP
        elif type == 0x806 :
            count += 1
            display = count
            row = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row)
            self.tableWidget.setItem(row,0, QtWidgets.QTableWidgetItem(str(count)))
            self.tableWidget.setItem(row,1,QtWidgets.QTableWidgetItem(str(packetTime)))
            self.tableWidget.setItem(row,2, QtWidgets.QTableWidgetItem(packet[ARP].psrc))
            self.tableWidget.setItem(row,3, QtWidgets.QTableWidgetItem(packet[ARP].pdst))
            self.tableWidget.setItem(row,4, QtWidgets.QTableWidgetItem('ARP'))
            self.tableWidget.setItem(row,5, QtWidgets.QTableWidgetItem(str(len(packet))))
            if packet[ARP].op == 1:  #request
                self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('Who has %s? Tell %s' % (packet[ARP].pdst,packet[ARP].psrc)))
            elif packet[ARP].op == 2:  #reply
                self.tableWidget.setItem(row,6, QtWidgets.QTableWidgetItem('%s is at %s' % (packet[ARP].psrc,packet[ARP].hwsrc)))
            self.tableWidget.setItem(row,7, QtWidgets.QTableWidgetItem(raw(packet).decode('Windows-1252','ignore')))

            #着色分析
            self.colorItem(row,packet)

            #加入packetList中
            self.packetList.append(packet)


    #着色分析
    def colorItem(self,row,packet):
        type = packet.type
        #IP
        if type == 0x800 :
            #IP坏包
            if packet.haslayer('IP') == 0:
                for i in range(7):
                    self.tableWidget.item(row,i).setBackground(Qt.black)   #设置背景颜色
                    self.tableWidget.item(row,i).setForeground(Qt.red)     #设置字体颜色
            #TCP
            if packet[IP].proto == 6:
                #HTTP
                if packet[TCP].dport == 80 or packet[TCP].sport == 80:
                    #HTTP坏包
                    if packet.haslayer('HTTP') == 0:
                        for i in range(7):
                            self.tableWidget.item(row,i).setBackground(Qt.black)   #设置背景颜色
                            self.tableWidget.item(row,i).setForeground(Qt.red)     #设置字体颜色
                    else:
                        for i in range(7):
                            self.tableWidget.item(row,i).setBackground(QColor('#99FF99'))   #设置背景颜色
                else:
                    #TCP坏包
                    if packet.haslayer('TCP') == 0:
                        for i in range(7):
                            self.tableWidget.item(row,i).setBackground(Qt.black)   #设置背景颜色
                            self.tableWidget.item(row,i).setForeground(Qt.red)     #设置字体颜色
                    #TCP SYN/FIN
                    elif packet[TCP].flags.S or packet[TCP].flags.F:
                        for i in range(7):
                            self.tableWidget.item(row,i).setBackground(QColor('#646464'))   #设置背景颜色
                    #TCP RST
                    elif packet[TCP].flags.R:
                        for i in range(7):
                            self.tableWidget.item(row,i).setBackground(QColor('#990000'))   #设置背景颜色
                            self.tableWidget.item(row,i).setForeground(QColor('#FFCC33'))     #设置字体颜色
                    else:
                        for i in range(7):
                            self.tableWidget.item(row,i).setBackground(QColor('#DDDDDD'))   #设置背景颜色
            #UDP
            elif packet[IP].proto == 17:
                #UDP坏包
                if packet.haslayer('UDP') == 0:
                    for i in range(7):
                        self.tableWidget.item(row,i).setBackground(Qt.black)   #设置背景颜色
                        self.tableWidget.item(row,i).setForeground(Qt.red)     #设置字体颜色
                else:
                    for i in range(7):
                        self.tableWidget.item(row,i).setBackground(QColor('#CCFFFF'))   #设置背景颜色
            #ICMP
            elif packet[IP].proto == 1:
                #ICMP坏包
                if packet.haslayer('ICMP') == 0:
                    for i in range(7):
                        self.tableWidget.item(row,i).setBackground(Qt.black)   #设置背景颜色
                        self.tableWidget.item(row,i).setForeground(Qt.red)     #设置字体颜色
                #ICMP errors
                elif packet[ICMP].type == 3 or packet[ICMP].type == 4 or packet[ICMP].type == 5 or packet[ICMP].type == 11:
                    for i in range(7):
                        self.tableWidget.item(row,i).setBackground(Qt.black)   #设置背景颜色
                        self.tableWidget.item(row,i).setForeground(QColor('#66FF66'))     #设置字体颜色
            #IGMP
            elif packet[IP].proto == 2:
                for i in range(7):
                    self.tableWidget.item(row,i).setBackground(QColor('#FFCCFF'))   #设置背景颜色
        #ARP
        elif type == 0x806 :
            #ARP坏包
            if packet.haslayer('ARP') == 0:
                for i in range(7):
                    self.tableWidget.item(row,i).setBackground(Qt.black)   #设置背景颜色
                    self.tableWidget.item(row,i).setForeground(Qt.red)     #设置字体颜色
            else:
                for i in range(7):
                    self.tableWidget.item(row,i).setBackground(QColor('#FFFFCC'))   #设置背景颜色

    #停止捕获
    def Stop(self):
        self.SnifferThread.terminate()

    #鼠标左键单击显示详细信息
    def clickInfo(self):
        row = self.tableWidget.currentRow()     #获取当前行数
        p = self.tableWidget.item(row,7).text()
        packet = scapy.layers.l2.Ether(p.encode('Windows-1252'))

        num = self.tableWidget.item(row,0).text()
        Time = self.tableWidget.item(row,1).text()
        length = self.tableWidget.item(row,5).text()
        iface = self.iface
        import time
        timeformat = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(packet.time))


        #packet.show()

        self.treeWidget.clear()
        self.treeWidget.setColumnCount(1)

        #Frame
        Frame = QtWidgets.QTreeWidgetItem(self.treeWidget)
        Frame.setText(0,'Frame %s：%s bytes on %s' % (num,length,iface))
        FrameIface = QtWidgets.QTreeWidgetItem(Frame)
        FrameIface.setText(0,'网卡设备：%s' % iface)
        FrameArrivalTime = QtWidgets.QTreeWidgetItem(Frame)
        FrameArrivalTime.setText(0,'到达时间：%s' % timeformat)
        FrameTime = QtWidgets.QTreeWidgetItem(Frame)
        FrameTime.setText(0,'距离第一帧时间：%s' % Time)
        FrameNumber = QtWidgets.QTreeWidgetItem(Frame)
        FrameNumber.setText(0,'序号：%s' % num)
        FrameLength = QtWidgets.QTreeWidgetItem(Frame)
        FrameLength.setText(0,'帧长度：%s' % length)


        #Ethernet
        Ethernet = QtWidgets.QTreeWidgetItem(self.treeWidget)
        Ethernet.setText(0,'Ethernet，源MAC地址(src)：'+ packet.src + '，目的MAC地址(dst)：'+packet.dst)
        EthernetDst = QtWidgets.QTreeWidgetItem(Ethernet)
        EthernetDst.setText(0,'目的MAC地址(dst)：'+ packet.dst)
        EthernetSrc = QtWidgets.QTreeWidgetItem(Ethernet)
        EthernetSrc.setText(0,'源MAC地址(src)：'+ packet.src)

        try:
            type = packet.type
        except:
            type = 0
        #IP
        if type == 0x800 :
            EthernetType = QtWidgets.QTreeWidgetItem(Ethernet)
            EthernetType.setText(0,'协议类型(type)：IPv4(0x800)')

            IPv4 = QtWidgets.QTreeWidgetItem(self.treeWidget)
            IPv4.setText(0,'IPv4，源地址(src)：'+packet[IP].src+'，目的地址(dst)：'+packet[IP].dst)
            IPv4Version = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Version.setText(0,'版本(version)：%s'% packet[IP].version)
            IPv4Ihl = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Ihl.setText(0,'包头长度(ihl)：%s' % packet[IP].ihl)
            IPv4Tos = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Tos.setText(0,'服务类型(tos)：%s'% packet[IP].tos)
            IPv4Len = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Len.setText(0,'总长度(len)：%s' % packet[IP].len) #IP报文的总长度。报头的长度和数据部分的长度之和。
            IPv4Id = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Id.setText(0,'标识(id)：%s' % packet[IP].id)  #唯一的标识主机发送的每一分数据报。通常每发送一个报文，它的值加一。当IP报文长度超过传输网络的MTU（最大传输单元）时必须分片，这个标识字段的值被复制到所有数据分片的标识字段中，使得这些分片在达到最终目的地时可以依照标识字段的内容重新组成原先的数据。
            IPv4Flags = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Flags.setText(0,'标志(flags)：%s' % packet[IP].flags) #R、DF、MF三位。目前只有后两位有效，DF位：为1表示不分片，为0表示分片。MF：为1表示“更多的片”，为0表示这是最后一片。
            IPv4Frag = QtWidgets.QTreeWidgetItem(IPv4)

            IPv4FlagsDF = QtWidgets.QTreeWidgetItem(IPv4Flags)
            IPv4FlagsDF.setText(0,'不分段(DF)：%s' % packet[IP].flags.DF)
            IPv4FlagsMF = QtWidgets.QTreeWidgetItem(IPv4Flags)
            IPv4FlagsMF.setText(0,'更多分段(MF)：%s' % packet[IP].flags.MF)

            IPv4Frag.setText(0,'片位移(frag)：%s ' % packet[IP].frag)  #本分片在原先数据报文中相对首位的偏移位。（需要再乘以8）
            IPv4Ttl = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Ttl.setText(0,'生存时间(ttl)：%s' % packet[IP].ttl)

            #TCP
            if packet[IP].proto == 6:
                if packet.haslayer('TCP'):
                    IPv4Proto = QtWidgets.QTreeWidgetItem(IPv4)
                    IPv4Proto.setText(0,'协议类型(proto)：TCP(6)')
                    tcp = QtWidgets.QTreeWidgetItem(self.treeWidget)
                    tcp.setText(0,'TCP，源端口(sport)：%s，目的端口(dport)：%s，Seq：%s，Ack：%s' % (packet[TCP].sport,packet[TCP].dport,packet[TCP].seq,packet[TCP].ack))
                    tcpSport = QtWidgets.QTreeWidgetItem(tcp)
                    tcpSport.setText(0,'源端口(sport)：%s' % packet[TCP].sport)
                    tcpDport = QtWidgets.QTreeWidgetItem(tcp)
                    tcpDport.setText(0,'目的端口(dport)：%s' % packet[TCP].dport)
                    tcpSeq = QtWidgets.QTreeWidgetItem(tcp)
                    tcpSeq.setText(0,'序号(Seq)：%s' % packet[TCP].seq)
                    tcpAck = QtWidgets.QTreeWidgetItem(tcp)
                    tcpAck.setText(0,'确认号(Ack)：%s' % packet[TCP].ack)
                    tcpDataofs = QtWidgets.QTreeWidgetItem(tcp)
                    tcpDataofs.setText(0,'数据偏移(dataofs)：%s' % packet[TCP].dataofs)
                    tcpReserved = QtWidgets.QTreeWidgetItem(tcp)
                    tcpReserved.setText(0,'保留(reserved)：%s' % packet[TCP].reserved)
                    tcpFlags = QtWidgets.QTreeWidgetItem(tcp)
                    tcpFlags.setText(0,'标志(flags)：%s' % packet[TCP].flags)
                    '''
                    ACK 置1时表示确认号（为合法，为0的时候表示数据段不包含确认信息，确认号被忽略。
                    RST 置1时重建连接。如果接收到RST位时候，通常发生了某些错误。
                    SYN 置1时用来发起一个连接。
                    FIN 置1时表示发端完成发送任务。用来释放连接，表明发送方已经没有数据发送了。
                    URG 紧急指针，告诉接收TCP模块紧要指针域指着紧要数据。注：一般不使用。
                    PSH 置1时请求的数据段在接收方得到后就可直接送到应用程序，而不必等到缓冲区满时才传送。注：一般不使用。
                  '''
                    tcpFlagsACK = QtWidgets.QTreeWidgetItem(tcpFlags)
                    tcpFlagsACK.setText(0,'确认(ACK)：%s' % packet[TCP].flags.A)
                    tcpFlagsRST = QtWidgets.QTreeWidgetItem(tcpFlags)
                    tcpFlagsRST.setText(0,'重新连接(RST)：%s' % packet[TCP].flags.R)
                    tcpFlagsSYN = QtWidgets.QTreeWidgetItem(tcpFlags)
                    tcpFlagsSYN.setText(0,'发起连接(SYN)：%s' % packet[TCP].flags.S)
                    tcpFlagsFIN = QtWidgets.QTreeWidgetItem(tcpFlags)
                    tcpFlagsFIN.setText(0,'释放连接(FIN)：%s' % packet[TCP].flags.F)
                    tcpFlagsURG = QtWidgets.QTreeWidgetItem(tcpFlags)
                    tcpFlagsURG.setText(0,'紧急指针(URG)：%s' % packet[TCP].flags.U)
                    tcpFlagsPSH = QtWidgets.QTreeWidgetItem(tcpFlags)
                    tcpFlagsPSH.setText(0,'非缓冲区(PSH)：%s' % packet[TCP].flags.P)
                    tcpWindow = QtWidgets.QTreeWidgetItem(tcp)
                    tcpWindow.setText(0,'窗口(window)：%s' % packet[TCP].window)
                    tcpChksum = QtWidgets.QTreeWidgetItem(tcp)
                    tcpChksum.setText(0,'校验和(chksum)：0x%x' % packet[TCP].chksum)
                    tcpUrgptr = QtWidgets.QTreeWidgetItem(tcp)
                    tcpUrgptr.setText(0,'紧急指针(urgptr)：%s' % packet[TCP].urgptr)  #只有当U R G标志置1时紧急指针才有效。紧急指针是一个正的偏移量，和序号字段中的值相加表示紧急数据最后一个字节的序号。
                    tcpOptions = QtWidgets.QTreeWidgetItem(tcp)
                    tcpOptions.setText(0,'选项(options)：%s' % packet[TCP].options)
                    '''
                    通常为空，可根据首部长度推算。用于发送方与接收方协商最大报文段长度（MSS），或在高速网络环境下作窗口调节因子时使用。首部字段还定义了一个时间戳选项。
                    最常见的可选字段是最长报文大小，又称为MSS (Maximum Segment Size)。每个连接方通常都在握手的第一步中指明这个选项。它指明本端所能接收的最大长度的报文段。1460是以太网默认的大小。
                  '''
                    #HTTP
                    if packet[TCP].dport == 80 or packet[TCP].sport == 80:
                        #HTTP Request
                        if packet.haslayer('HTTPRequest'):
                            http = QtWidgets.QTreeWidgetItem(self.treeWidget)
                            http.setText(0,'HTTP Request')
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Method%}") != 'None':
                                httpMethod = QtWidgets.QTreeWidgetItem(http)
                                httpMethod.setText(0,'Method：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Method%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Path%}") != 'None':
                                httpPath = QtWidgets.QTreeWidgetItem(http)
                                httpPath.setText(0,'Path：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Path%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Http-Version%}") != 'None':
                                httpHttpVersion = QtWidgets.QTreeWidgetItem(http)
                                httpHttpVersion.setText(0,'Http-Version：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Http-Version%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Host%}") != 'None':
                                httpHost = QtWidgets.QTreeWidgetItem(http)
                                httpHost.setText(0,'Host：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Host%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.User-Agent%}") != 'None':
                                httpUserAgent = QtWidgets.QTreeWidgetItem(http)
                                httpUserAgent.setText(0,'User-Agent：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.User-Agent%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Accept%}") != 'None':
                                httpAccept = QtWidgets.QTreeWidgetItem(http)
                                httpAccept.setText(0,'Accept：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Accept%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Accept-Language%}") != 'None':
                                httpAcceptLanguage = QtWidgets.QTreeWidgetItem(http)
                                httpAcceptLanguage.setText(0,'Accept-Language：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Accept-Language%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Accept-Encoding%}") != 'None':
                                httpAcceptEncoding = QtWidgets.QTreeWidgetItem(http)
                                httpAcceptEncoding.setText(0,'Accept-Encoding：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Accept-Encoding%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Accept-Charset%}") != 'None':
                                httpAcceptCharset = QtWidgets.QTreeWidgetItem(http)
                                httpAcceptCharset.setText(0,'Accept-Charset：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Accept-Charset%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Referer%}") != 'None':
                                httpReferer = QtWidgets.QTreeWidgetItem(http)
                                httpReferer.setText(0,'Referer：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Referer%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Authorization%}") != 'None':
                                httpAuthorization = QtWidgets.QTreeWidgetItem(http)
                                httpAuthorization.setText(0,'Authorization：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Authorization%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Expect%}") != 'None':
                                httpExpect = QtWidgets.QTreeWidgetItem(http)
                                httpExpect.setText(0,'Expect：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Expect%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.From%}") != 'None':
                                httpFrom = QtWidgets.QTreeWidgetItem(http)
                                httpFrom.setText(0,'From：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.From%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.If-Match%}") != 'None':
                                httpIfMatch = QtWidgets.QTreeWidgetItem(http)
                                httpIfMatch.setText(0,'If-Match：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.If-Match%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.If-Modified-Since%}") != 'None':
                                httpIfModifiedSince = QtWidgets.QTreeWidgetItem(http)
                                httpIfModifiedSince.setText(0,'If-Modified-Since：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.If-Modified-Since%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.If-None-Match%}") != 'None':
                                httpIfNoneMatch = QtWidgets.QTreeWidgetItem(http)
                                httpIfNoneMatch.setText(0,'If-None-Match：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.If-None-Match%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.If-Range%}") != 'None':
                                httpIfRange = QtWidgets.QTreeWidgetItem(http)
                                httpIfRange.setText(0,'If-Range：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.If-Range%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.If-Unmodified-Since%}") != 'None':
                                httpIfUnmodifiedSince = QtWidgets.QTreeWidgetItem(http)
                                httpIfUnmodifiedSince.setText(0,'If-Unmodified-Since：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.If-Unmodified-Since%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Max-Forwards%}") != 'None':
                                httpMaxForwards = QtWidgets.QTreeWidgetItem(http)
                                httpMaxForwards.setText(0,'Max-Forwards：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Max-Forwards%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Proxy-Authorization%}") != 'None':
                                httpProxyAuthorization = QtWidgets.QTreeWidgetItem(http)
                                httpProxyAuthorization.setText(0,'Proxy-Authorization：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Proxy-Authorization%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Range%}") != 'None':
                                httpRange = QtWidgets.QTreeWidgetItem(http)
                                httpRange.setText(0,'Range：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Range%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.TE%}") != 'None':
                                httpTE = QtWidgets.QTreeWidgetItem(http)
                                httpTE.setText(0,'TE：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.TE%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Cache-Control%}") != 'None':
                                httpCacheControl = QtWidgets.QTreeWidgetItem(http)
                                httpCacheControl.setText(0,'Cache-Control：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Cache-Control%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Connection%}") != 'None':
                                httpConnection = QtWidgets.QTreeWidgetItem(http)
                                httpConnection.setText(0,'Connection：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Connection%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Date%}") != 'None':
                                httpDate = QtWidgets.QTreeWidgetItem(http)
                                httpDate.setText(0,'Date：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Date%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Pragma%}") != 'None':
                                httpPragma = QtWidgets.QTreeWidgetItem(http)
                                httpPragma.setText(0,'Pragma：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Pragma%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Trailer%}") != 'None':
                                httpTrailer = QtWidgets.QTreeWidgetItem(http)
                                httpTrailer.setText(0,'Trailer：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Trailer%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Transfer-Encoding%}") != 'None':
                                httpTransferEncoding = QtWidgets.QTreeWidgetItem(http)
                                httpTransferEncoding.setText(0,'Transfer-Encoding：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Transfer-Encoding%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Upgrade%}") != 'None':
                                httpUpgrade = QtWidgets.QTreeWidgetItem(http)
                                httpUpgrade.setText(0,'Upgrade：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Upgrade%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Via%}") != 'None':
                                httpVia = QtWidgets.QTreeWidgetItem(http)
                                httpVia.setText(0,'Via：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Via%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Warning%}") != 'None':
                                httpWarning = QtWidgets.QTreeWidgetItem(http)
                                httpWarning.setText(0,'Warning：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Warning%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Keep-Alive%}") != 'None':
                                httpKeepAlive = QtWidgets.QTreeWidgetItem(http)
                                httpKeepAlive.setText(0,'Keep-Alive：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Keep-Alive%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Allow%}") != 'None':
                                httpAllow = QtWidgets.QTreeWidgetItem(http)
                                httpAllow.setText(0,'Allow：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Allow%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Encoding%}") != 'None':
                                httpContentEncoding = QtWidgets.QTreeWidgetItem(http)
                                httpContentEncoding.setText(0,'Content-Encoding：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Encoding%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Language%}") != 'None':
                                httpContentLanguage = QtWidgets.QTreeWidgetItem(http)
                                httpContentLanguage.setText(0,'Content-Language：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Language%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Length%}") != 'None':
                                httpContentLength = QtWidgets.QTreeWidgetItem(http)
                                httpContentLength.setText(0,'Content-Length：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Length%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Location%}") != 'None':
                                httpContentLocation = QtWidgets.QTreeWidgetItem(http)
                                httpContentLocation.setText(0,'Content-Location：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Location%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Content-MD5%}") != 'None':
                                httpContentMD5 = QtWidgets.QTreeWidgetItem(http)
                                httpContentMD5.setText(0,'Content-MD5：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Content-MD5%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Range%}") != 'None':
                                httpContentRange = QtWidgets.QTreeWidgetItem(http)
                                httpContentRange.setText(0,'Content-Range：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Range%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Type%}") != 'None':
                                httpContentType = QtWidgets.QTreeWidgetItem(http)
                                httpContentType.setText(0,'Content-Type：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Content-Type%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Expires%}") != 'None':
                                httpExpires = QtWidgets.QTreeWidgetItem(http)
                                httpExpires.setText(0,'Expires：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Expires%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Last-Modified%}") != 'None':
                                httpLastModified = QtWidgets.QTreeWidgetItem(http)
                                httpLastModified.setText(0,'Last-Modified：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Last-Modified%}").strip("'"))
                            if packet.sprintf("{HTTPRequest:%HTTPRequest.Cookie%}") != 'None':
                                httpCookie = QtWidgets.QTreeWidgetItem(http)
                                httpCookie.setText(0,'Cookie：%s' % packet.sprintf("{HTTPRequest:%HTTPRequest.Cookie%}").strip("'"))
                        #HTTP Response
                        if packet.haslayer('HTTPResponse'):
                            http = QtWidgets.QTreeWidgetItem(self.treeWidget)
                            http.setText(0,'HTTP Response')
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Status-Line%}") != 'None':
                                httpStatusLine = QtWidgets.QTreeWidgetItem(http)
                                httpStatusLine.setText(0,'Status-Line：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Status-Line%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Accept-Ranges%}") != 'None':
                                httpAcceptRanges = QtWidgets.QTreeWidgetItem(http)
                                httpAcceptRanges.setText(0,'Accept-Ranges：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Accept-Ranges%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Age%}") != 'None':
                                httpAge = QtWidgets.QTreeWidgetItem(http)
                                httpAge.setText(0,'Age：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Age%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.E-Tag%}") != 'None':
                                httpETag = QtWidgets.QTreeWidgetItem(http)
                                httpETag.setText(0,'E-Tag：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.E-Tag%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Location%}") != 'None':
                                httpLocation = QtWidgets.QTreeWidgetItem(http)
                                httpLocation.setText(0,'Location：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Location%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Proxy-Authenticate%}") != 'None':
                                httpProxyAuthenticate = QtWidgets.QTreeWidgetItem(http)
                                httpProxyAuthenticate.setText(0,'Proxy-Authenticate：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Proxy-Authenticate%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Retry-After%}") != 'None':
                                httpRetryAfter = QtWidgets.QTreeWidgetItem(http)
                                httpRetryAfter.setText(0,'Retry-After：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Retry-After%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Server%}") != 'None':
                                httpServer = QtWidgets.QTreeWidgetItem(http)
                                httpServer.setText(0,'Server：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Server%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Vary%}") != 'None':
                                httpVary = QtWidgets.QTreeWidgetItem(http)
                                httpVary.setText(0,'Vary：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Vary%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.WWW-Authenticate%}") != 'None':
                                httpWWWAuthenticate = QtWidgets.QTreeWidgetItem(http)
                                httpWWWAuthenticate.setText(0,'WWW-Authenticate：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.WWW-Authenticate%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Cache-Control%}") != 'None':
                                httpCacheControl = QtWidgets.QTreeWidgetItem(http)
                                httpCacheControl.setText(0,'Cache-Control：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Cache-Control%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Connection%}") != 'None':
                                httpConnection = QtWidgets.QTreeWidgetItem(http)
                                httpConnection.setText(0,'Connection：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Connection%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Date%}") != 'None':
                                httpDate = QtWidgets.QTreeWidgetItem(http)
                                httpDate.setText(0,'Date：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Date%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Pragma%}") != 'None':
                                httpPragma = QtWidgets.QTreeWidgetItem(http)
                                httpPragma.setText(0,'Pragma：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Pragma%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Trailer%}") != 'None':
                                httpTrailer = QtWidgets.QTreeWidgetItem(http)
                                httpTrailer.setText(0,'Trailer：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Trailer%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Transfer-Encoding%}") != 'None':
                                httpTransferEncoding = QtWidgets.QTreeWidgetItem(http)
                                httpTransferEncoding.setText(0,'Transfer-Encoding：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Transfer-Encoding%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Upgrade%}") != 'None':
                                httpUpgrade = QtWidgets.QTreeWidgetItem(http)
                                httpUpgrade.setText(0,'Upgrade：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Upgrade%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Via%}") != 'None':
                                httpVia = QtWidgets.QTreeWidgetItem(http)
                                httpVia.setText(0,'Via：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Via%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Warning%}") != 'None':
                                httpWarning = QtWidgets.QTreeWidgetItem(http)
                                httpWarning.setText(0,'Warning：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Warning%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Keep-Alive%}") != 'None':
                                httpKeepAlive = QtWidgets.QTreeWidgetItem(http)
                                httpKeepAlive.setText(0,'Keep-Alive：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Keep-Alive%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Allow%}") != 'None':
                                httpAllow = QtWidgets.QTreeWidgetItem(http)
                                httpAllow.setText(0,'Allow：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Allow%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Encoding%}") != 'None':
                                httpContentEncoding = QtWidgets.QTreeWidgetItem(http)
                                httpContentEncoding.setText(0,'Content-Encoding：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Encoding%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Language%}") != 'None':
                                httpContentLanguage = QtWidgets.QTreeWidgetItem(http)
                                httpContentLanguage.setText(0,'Content-Language：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Language%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Length%}") != 'None':
                                httpContentLength = QtWidgets.QTreeWidgetItem(http)
                                httpContentLength.setText(0,'Content-Length：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Length%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Location%}") != 'None':
                                httpContentLocation = QtWidgets.QTreeWidgetItem(http)
                                httpContentLocation.setText(0,'Content-Location：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Location%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Content-MD5%}") != 'None':
                                httpContentMD5 = QtWidgets.QTreeWidgetItem(http)
                                httpContentMD5.setText(0,'Content-MD5：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Content-MD5%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Range%}") != 'None':
                                httpContentRange = QtWidgets.QTreeWidgetItem(http)
                                httpContentRange.setText(0,'Content-Range：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Range%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Type%}") != 'None':
                                httpContentType = QtWidgets.QTreeWidgetItem(http)
                                httpContentType.setText(0,'Content-Type：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Content-Type%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Expires%}") != 'None':
                                httpExpires = QtWidgets.QTreeWidgetItem(http)
                                httpExpires.setText(0,'Expires：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Expires%}").strip("'"))
                            if packet.sprintf("{HTTPResponse:%HTTPResponse.Last-Modified%}") != 'None':
                                httpLastModified = QtWidgets.QTreeWidgetItem(http)
                                httpLastModified.setText(0,'Last-Modified：%s' % packet.sprintf("{HTTPResponse:%HTTPResponse.Last-Modified%}").strip("'"))


            #UDP
            elif packet[IP].proto == 17:
                IPv4Proto = QtWidgets.QTreeWidgetItem(IPv4)
                IPv4Proto.setText(0,'协议类型(proto)：UDP(17)')
                udp = QtWidgets.QTreeWidgetItem(self.treeWidget)
                udp.setText(0,'UDP，源端口(sport)：%s，目的端口(dport)：%s'% (packet[UDP].sport , packet[UDP].dport))
                udpSport = QtWidgets.QTreeWidgetItem(udp)
                udpSport.setText(0,'源端口(sport)：%s' % packet[UDP].sport)
                udpDport = QtWidgets.QTreeWidgetItem(udp)
                udpDport.setText(0,'目的端口(dport)：%s' % packet[UDP].dport)
                udpLen = QtWidgets.QTreeWidgetItem(udp)
                udpLen.setText(0,'长度(len)：%s' % packet[UDP].len)
                udpChksum = QtWidgets.QTreeWidgetItem(udp)
                udpChksum.setText(0,'校验和(chksum)：0x%x' % packet[UDP].chksum)
                #DNS
                if packet.haslayer('DNS'):
                    pass
                    # nds = QtWidgets.QTreeWidgetItem(self.treeWidget)
                    # nds.setText(0,'DNS')
            #ICMP
            elif packet[IP].proto == 1:
                IPv4Proto = QtWidgets.QTreeWidgetItem(IPv4)
                IPv4Proto.setText(0,'协议类型(proto)：ICMP(1)')

                '''
                8位类型和8位代码字段一起决定了ICMP报文的类型。
                    类型8，代码0：表示回显请求(ping请求)。
                    类型0，代码0：表示回显应答(ping应答)
                    类型11，代码0：超时
               '''
                icmp = QtWidgets.QTreeWidgetItem(self.treeWidget)
                icmp.setText(0,'ICMP')
                icmpType = QtWidgets.QTreeWidgetItem(icmp)
                if packet[ICMP].type == 8:
                    icmpType.setText(0,'类型(type)：%s (Echo (ping) request)' % packet[ICMP].type)
                elif packet[ICMP].type == 0:
                    icmpType.setText(0,'类型(type)：%s (Echo (ping) reply)' % packet[ICMP].type)
                else:
                    icmpType.setText(0,'类型(type)：%s' % packet[ICMP].type)  #占一字节，标识ICMP报文的类型，目前已定义了14种，从类型值来看ICMP报文可以分为两大类。第一类是取值为1~127的差错报文，第2类是取值128以上的信息报文。
                icmpCode = QtWidgets.QTreeWidgetItem(icmp)
                icmpCode.setText(0,'代码(code)：%s' % packet[ICMP].code)  #占一字节，标识对应ICMP报文的代码。它与类型字段一起共同标识了ICMP报文的详细类型。
                icmpChksum = QtWidgets.QTreeWidgetItem(icmp)
                icmpChksum.setText(0,'校验和(chksum)：0x%x' % packet[ICMP].chksum)
                icmpId = QtWidgets.QTreeWidgetItem(icmp)
                icmpId.setText(0,'标识(id)：%s' % packet[ICMP].id)  #占两字节，用于标识本ICMP进程，但仅适用于回显请求和应答ICMP报文，对于目标不可达ICMP报文和超时ICMP报文等，该字段的值为0。
                icmpSeq = QtWidgets.QTreeWidgetItem(icmp)
                icmpSeq.setText(0,'seq：%s' % packet[ICMP].seq)
                icmpTs_ori = QtWidgets.QTreeWidgetItem(icmp)
                icmpTs_ori.setText(0,'ts_ori：%s' % packet[ICMP].ts_ori)
                icmpTs_rx = QtWidgets.QTreeWidgetItem(icmp)
                icmpTs_rx.setText(0,'ts_rx：%s' % packet[ICMP].ts_rx)
                icmpTs_tx = QtWidgets.QTreeWidgetItem(icmp)
                icmpTs_tx.setText(0,'ts_tx：%s' % packet[ICMP].ts_tx)
                icmpGw = QtWidgets.QTreeWidgetItem(icmp)
                icmpGw.setText(0,'gw：%s' % packet[ICMP].gw)
                icmpPtr = QtWidgets.QTreeWidgetItem(icmp)
                icmpPtr.setText(0,'ptr：%s' % packet[ICMP].ptr)
                icmpReserved = QtWidgets.QTreeWidgetItem(icmp)
                icmpReserved.setText(0,'reserved：%s' % packet[ICMP].reserved)
                icmpLength = QtWidgets.QTreeWidgetItem(icmp)
                icmpLength.setText(0,'length：%s' % packet[ICMP].length)
                icmpAddr_mask = QtWidgets.QTreeWidgetItem(icmp)
                icmpAddr_mask.setText(0,'addr_mask：%s' % packet[ICMP].addr_mask)
                icmpnexthopmtu = QtWidgets.QTreeWidgetItem(icmp)
                icmpnexthopmtu.setText(0,'nexthopmtu：%s' % packet[ICMP].nexthopmtu)
            #IGMP
            elif packet[IP].proto == 2:
                IPv4Proto = QtWidgets.QTreeWidgetItem(IPv4)
                IPv4Proto.setText(0,'协议类型(proto)：IGMP(2)')

                igmp = QtWidgets.QTreeWidgetItem(self.treeWidget)
                igmp.setText(0,'IGMP')
                igmpCopy_flag = QtWidgets.QTreeWidgetItem(igmp)
                igmpCopy_flag.setText(0,'copy_flag：%s' % packet[IPOption_Router_Alert].copy_flag)
                igmpOptclass = QtWidgets.QTreeWidgetItem(igmp)
                igmpOptclass.setText(0,'optclass：%s' % packet[IPOption_Router_Alert].optclass)
                igmpOption = QtWidgets.QTreeWidgetItem(igmp)
                igmpOption.setText(0,'option：%s' % packet[IPOption_Router_Alert].option)
                igmpLength = QtWidgets.QTreeWidgetItem(igmp)
                igmpLength.setText(0,'length：%s' % packet[IPOption_Router_Alert].length)
                igmpAlert = QtWidgets.QTreeWidgetItem(igmp)
                igmpAlert.setText(0,'alert：%s' % packet[IPOption_Router_Alert].alert)
            else:
                IPv4Proto = QtWidgets.QTreeWidgetItem(IPv4)
                IPv4Proto.setText(0,'协议类型(proto)：%s'% packet[IP].proto)


            IPv4Chksum = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Chksum.setText(0,'校验和(chksum)：0x%x' % packet[IP].chksum)
            IPv4Src = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Src.setText(0,'源IP地址(src)：%s' % packet[IP].src)
            IPv4Dst = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Dst.setText(0,'目的IP地址(dst)：%s' % packet[IP].dst)
            IPv4Options = QtWidgets.QTreeWidgetItem(IPv4)
            IPv4Options.setText(0,'可选部分(options)：%s' %packet[IP].options)

        #ARP
        elif type == 0x806 :
            EthernetType = QtWidgets.QTreeWidgetItem(Ethernet)
            EthernetType.setText(0,'协议类型(type)：ARP(0x806)')

            arp = QtWidgets.QTreeWidgetItem(self.treeWidget)
            arp.setText(0,'ARP')
            arpHwtype = QtWidgets.QTreeWidgetItem(arp)
            arpHwtype.setText(0,'硬件类型(hwtype)：0x%x' % packet[ARP].hwtype) #1代表是以太网。
            arpPtype = QtWidgets.QTreeWidgetItem(arp)
            arpPtype.setText(0,'协议类型(ptype)：0x%x' % packet[ARP].ptype) #表明上层协议的类型,这里是0x0800,表示上层协议是IP协议
            arpHwlen = QtWidgets.QTreeWidgetItem(arp)
            arpHwlen.setText(0,'硬件地址长度(hwlen)：%s' % packet[ARP].hwlen)
            arpPlen = QtWidgets.QTreeWidgetItem(arp)
            arpPlen.setText(0,'协议长度(plen)：%s' % packet[ARP].plen)
            arpOp = QtWidgets.QTreeWidgetItem(arp)
            if packet[ARP].op == 1:  #request
                arpOp.setText(0,'操作类型(op)：request (%s)' % packet[ARP].op)
            elif packet[ARP].op == 2:
                arpOp.setText(0,'操作类型(op)：reply (%s)' % packet[ARP].op)
            else:
                arpOp.setText(0,'操作类型(op)：%s' % packet[ARP].op) #在报文中占2个字节,1表示ARP请求,2表示ARP应答,3表示RARP请求,4表示RARP应答
            arpHwsrc = QtWidgets.QTreeWidgetItem(arp)
            arpHwsrc.setText(0,'源MAC地址(hwsrc)：%s' % packet[ARP].hwsrc)
            arpPsrc = QtWidgets.QTreeWidgetItem(arp)
            arpPsrc.setText(0,'源IP地址(psrc)：%s' % packet[ARP].psrc)
            arpHwdst = QtWidgets.QTreeWidgetItem(arp)
            arpHwdst.setText(0,'目的MAC地址(hwdst)：%s' % packet[ARP].hwdst)
            arpPdst = QtWidgets.QTreeWidgetItem(arp)
            arpPdst.setText(0,'目的IP地址(pdst)：%s' % packet[ARP].pdst)

        self.textBrowserRaw.clear()
        if packet.haslayer('Raw'):
            # raw = QtWidgets.QTreeWidgetItem(self.treeWidget)
            # raw.setText(0,'Raw：%s' % packet[Raw].load.decode('utf-8','ignore'))
            self.textBrowserRaw.append('Raw：%s' % packet[Raw].load.decode('utf-8','ignore'))

        if packet.haslayer('Padding'):
            # padding = QtWidgets.QTreeWidgetItem(self.treeWidget)
            # padding.setText(0,'Padding：%s' % packet[Padding].load.decode('utf-8','ignore'))
            self.textBrowserRaw.append('Padding：%s' % packet[Padding].load.decode('utf-8','ignore'))

        self.textBrowserDump.clear()
        f = open('hexdump.tmp','w')
        old = sys.stdout #将当前系统输出储存到临时变量
        sys.stdout = f   #输出重定向到文件
        hexdump(packet)
        sys.stdout = old
        f.close()
        f = open('hexdump.tmp','r')
        content = f.read()
        self.textBrowserDump.append(content)
        f.close()
        os.remove('hexdump.tmp')



    #遍历网卡
    def LookupIface(self):
        # netcards = os.listdir('/sys/class/net/')
        netcards = ['aaa', 'bbb', 'ccc']
        eth_local=[]
        # a = repr(conf.route).split('\n')[1:]
        # for x in a:
        #     b = re.search(r'[a-zA-Z](.*)[a-zA-Z]',x)
        #     eth_local.append(b.group())
        # #去重
        # c = []
        # c.append(eth_local[0])
        # for i in range(0,len(eth_local),1):
        #     m = 0
        #     for j in range(0,len(c),1):
        #         if c[j] == eth_local[i]:
        #             m += 1
        #     if m==0:
        #         c.append(eth_local[i])
        # #添加到comboBoxIface中
        self.comboBoxIface.addItems(netcards)
    #捕获过滤
    def PreFilter(self):
        list = ["指定源IP地址","指定目的IP地址", "指定源端口","指定目的端口","指定协议类型","自定义规则"]

         #第三个参数可选 有一般显示 （QLineEdit.Normal）、密碼显示（ QLineEdit. Password）与不回应文字输入（ QLineEdit. NoEcho）
        #stringNum,ok3 = QInputDialog.getText(self, "标题","姓名:",QLineEdit.Normal, "王尼玛")
         #1为默认选中选项目，True/False  列表框是否可编辑。
        item, ok = QInputDialog.getItem(self, "选项","规则列表", list, 1, False)
        type=0
        if ok:
            if item=="指定源IP地址":
                 filter,ok_1 = QInputDialog.getText(self, "标题","请输入指定源IP地址:",QLineEdit.Normal, "*.*.*.*")
                 rule = "src host "+filter
            elif item =="指定目的IP地址"  :
                 filter,ok_2 = QInputDialog.getText(self, "标题","请输入指定目的IP地址:",QLineEdit.Normal, "*.*.*.*")
                 rule= "dst host "+filter
            elif item =="指定源端口":
                 filter,ok_3 = QInputDialog.getInt(self, "标题","请输入指定源端口:",80, 0, 65535)
                 rule="src port "+str(filter)
            elif item =="指定目的端口":
                 filter,ok_4 = QInputDialog.getInt(self, "标题","请输入指定目的端口:",80, 0, 65535)
                 rule ="dst port "+str(filter)
            elif item =="指定协议类型" :
                 filter,ok_2 = QInputDialog.getText(self, "标题","请输入指定协议类型:",QLineEdit.Normal, "icmp")
                 rule =filter
            elif item =="自定义规则":
                 filter,ok_2 = QInputDialog.getText(self, "标题","请输入规则:",QLineEdit.Normal, "host 202.120.2.1")
                 rule=filter
            rule=rule.lower()
            self.setPreFilter(rule)

    def setPreFilter(self,filter):
        self.filter = filter

    #显示过滤
    def PostFilter(self):
        filter,ok = QInputDialog.getText(self, "过滤前需要停止抓包","请输入需要搜索的字段:",QLineEdit.Normal, "http")
        if ok:
            global display
            display = 0
            if filter == None:
                for row in range(self.tableWidget.rowCount()):
                    self.tableWidget.setRowHidden(row,True)
                    display += 1
            else:
                for row in range(self.tableWidget.rowCount()):
                    if(self.tableWidget.item(row, 7))!=None:
                        p = self.tableWidget.item(row,7).text()
                        packet = scapy.layers.l2.Ether(p.encode('Windows-1252'))

                        f = open('search.tmp','w')
                        old = sys.stdout #将当前系统输出储存到临时变量
                        sys.stdout = f   #输出重定向到文件
                        packet.show()
                        sys.stdout = old
                        f.close()
                        f = open('search.tmp','r')
                        data = f.read()
                        f.close()
                        os.remove('search.tmp')
                        obj= re.search(filter.lower(),data.lower())
                        if  obj is None:
                            self.tableWidget.setRowHidden(row,True)
                            display += 1
                        else:
                            self.tableWidget.setRowHidden(row,False)
    #数据包统计
    def statistics(self):
        global count
        global display
        if count != 0:
            percent = '{:.1f}'.format(display/count*100)
            self.statusbar.showMessage('捕获：%s   已显示：%s (%s%%)' % (count,display,percent))



#嗅探线程
class SnifferThread(QtCore.QThread):
    HandleSignal = QtCore.pyqtSignal(scapy.layers.l2.Ether)

    def __init__(self,filter,iface):
        super().__init__()
        self.filter = filter
        self.iface = iface

    def run(self):
        sniff(filter=self.filter,iface=self.iface,prn=lambda x:self.HandleSignal.emit(x))

    # def pack_callback(self,packet):
    #     packet.show()

#pdfdump线程
class pdfdumpThread(QtCore.QThread):

    pdfdumpSignal = QtCore.pyqtSignal(bool)
    def __init__(self,packet,path):
        super().__init__()
        self.packet = packet
        self.path = path

    def run(self):
        self.packet.pdfdump(self.path,layer_shift=1)
        self.pdfdumpSignal.emit(True)




if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = SnifferMainWindow()
    ui.setupUi(MainWindow)
    ui.setSlot()
    MainWindow.show()
    sys.exit(app.exec())
