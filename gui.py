#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :  gui.py
@Date    :  2023/04/06
@Author  :  Yaronzz
@Version :  1.0
@Contact :  yaronhuang@foxmail.com
@Desc    :  
"""

import time
import sys
import _thread

import utils.functions as ft
from api.chaoxing import Chaoxing

from PyQt5.QtCore import Qt, QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5 import QtWidgets
from qt_material import apply_stylesheet

ft.init_all_path(["saves", "logs"])  # 检查文件夹
logger = ft.Logger("main", False, True)  # 初始化日志类
chaoxing = Chaoxing("", "", False, True)     # 实例化超星API
chaoxing.init_explorer()
chaoxing.speed = 1

def do_work(chaoxingAPI):
    re_login_try = 0
    # done = list(ft.load_finished(chaoxingAPI.usernm))
    logger.info("已选课程："+str(chaoxingAPI.selected_course['content']['course']['data'][0]['name']))
    logger.info("开始获取所有章节")
    chaoxingAPI.get_selected_course_data()  # 读取所有章节
    mission_num = len(chaoxingAPI.missions)
    mission_index = 0
    while mission_index < mission_num:
        mission = chaoxingAPI.missions[mission_index]
        mission_index += 1
        logger.debug("开始读取章节信息")
        knowledge_raw = chaoxingAPI.get_mission(mission['id'], chaoxingAPI.selected_course['key'])  # 读取章节信息
        if "data" not in knowledge_raw and "error" in knowledge_raw:
            logger.debug("---knowledge_raw info begin---")
            logger.debug(knowledge_raw)
            logger.debug("---knowledge_raw info end---")
            if re_login_try < 2:
                logger.warn("章节数据错误,可能是课程存在验证码,正在尝试重新登录")
                chaoxingAPI.re_init_login()
                mission_index -= 1
                re_login_try += 1
                continue
            else:
                logger.error("章节数据错误,可能是课程存在验证码,重新登录尝试无效")
                input("请截图并携带日志提交Issue反馈")
        re_login_try = 0
        tabs = len(knowledge_raw['data'][0]['card']['data'])
        for tab_index in range(tabs):
            print("开始读取标签信息")
            knowledge_card_text = chaoxingAPI.get_knowledge(
                chaoxingAPI.selected_course['key'],
                chaoxingAPI.selected_course['content']['course']['data'][0]['id'],
                mission["id"],
                tab_index
            )
            attachments: dict = chaoxingAPI.get_attachments(knowledge_card_text)
            if not attachments:
                continue
            if not attachments.get('attachments'):
                continue
            print(f'\n当前章节：{mission["label"]}:{mission["name"]}')
            for attachment in attachments['attachments']:
                if attachment.get('type') != 'video':  # 非视频任务跳过
                    print("跳过非视频任务")
                    continue
                if attachment.get('property', False):
                    name = attachment['property']['name']
                else:
                    name = attachment['objectId']
                print(f"\n当前视频：{name}")
                if attachment.get('isPassed'):
                    print("当前视频任务已完成")
                    ft.show_progress(name, 1, 1)
                    time.sleep(1)
                    continue
                video_info = chaoxingAPI.get_d_token(
                    attachment['objectId'],
                    attachments['defaults']['fid']
                )
                if not video_info:
                    continue
                jobid = None
                if "jobid" in attachments:
                    jobid = attachments["jobid"]
                else:
                    if "jobid" in attachment:
                        jobid = attachment["jobid"]
                    elif attachment.get('property', False):
                        if "jobid" in attachment['property']:
                            jobid = attachment['property']['jobid']
                        else:
                            if "'_jobid'" in attachment['property']:
                                jobid = attachment['property']['_jobid']
                if not jobid:
                    print("未找到jobid，已跳过当前任务点")
                    continue
                # if adopt:
                #     logger.debug("已启用自适应速率")
                #     if "doublespeed" in attachment['property']:
                #         if attachment['property']['doublespeed']:
                #             print("当前视频支持倍速播放,已切换速率")
                #             chaoxing.speed = 2
                #     else:
                #         print("当前视频不支持倍速播放,跳过")
                #         chaoxing.speed = set_speed
                dtype = 'Video'
                if 'audio' in attachment['property']['module']:
                    dtype = 'Audio'

                chaoxingAPI.pass_video(
                    video_info['duration'],
                    attachments['defaults']['cpi'],
                    video_info['dtoken'],
                    attachment['otherInfo'],
                    chaoxingAPI.selected_course['key'],
                    attachment['jobid'],
                    video_info['objectid'],
                    chaoxingAPI.uid,
                    attachment['property']['name'],
                    chaoxingAPI.speed,
                    dtype,
                    chaoxingAPI.get_current_ms
                )
                ft.pause(10, 13)
                # chaoxing.speed = set_speed  # 预防ERR


class EmittingStream( QObject):
    textWritten = pyqtSignal(str)

    def write(self, text):
        self.textWritten.emit(str(text))

class MainView(QtWidgets.QWidget):
    s_startEnd = pyqtSignal(str, bool)

    def __init__(self, ) -> None:
        super().__init__()
        self.initView()
        self.setMinimumSize(700, 500)
        self.setWindowTitle("chaoXing")

    def __output__(self, text):
        cursor = self.c_printTextEdit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.c_printTextEdit.setTextCursor(cursor)
        self.c_printTextEdit.ensureCursorVisible()
        
    def initView(self):
        self.c_btnStart = QtWidgets.QPushButton("开始")

        columnNames = ['#', '课程']
        self.c_tableInfo = QtWidgets.QTableWidget()
        self.c_tableInfo.setColumnCount(len(columnNames))
        self.c_tableInfo.setRowCount(0)
        self.c_tableInfo.setShowGrid(False)
        self.c_tableInfo.verticalHeader().setVisible(False)
        self.c_tableInfo.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.c_tableInfo.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.c_tableInfo.horizontalHeader().setStretchLastSection(True)
        self.c_tableInfo.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.c_tableInfo.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.c_tableInfo.setFocusPolicy(Qt.NoFocus)
        for index, name in enumerate(columnNames):
            item = QtWidgets.QTableWidgetItem(name)
            self.c_tableInfo.setHorizontalHeaderItem(index, item)

        # print
        self.c_printTextEdit = QtWidgets.QTextEdit()
        self.c_printTextEdit.setReadOnly(True)
        self.c_printTextEdit.setFixedHeight(500)
        self.c_printTextEdit.setFixedWidth(500)
        sys.stdout = EmittingStream(textWritten=self.__output__)
        sys.stderr = EmittingStream(textWritten=self.__output__)

        self.lineGrid = QtWidgets.QVBoxLayout()
        self.lineGrid.addWidget(self.c_tableInfo)
        self.lineGrid.addWidget(self.c_btnStart)

        self.mainGrid = QtWidgets.QHBoxLayout(self)
        self.mainGrid.addLayout(self.lineGrid)
        self.mainGrid.addWidget(self.c_printTextEdit)

        self.c_btnStart.clicked.connect(self.start)
        self.s_startEnd.connect(self.startEnd)
        
    def refresh(self):
        if chaoxing.get_all_courses():
            self.c_tableInfo.setRowCount(len(chaoxing.courses))
            for course_index, course in enumerate(chaoxing.courses):
                if "course" in course["content"]:
                    self.addItem(course_index, 0, str(course_index + 1))
                    self.addItem(course_index, 1, str(course['content']['course']['data'][0]['name']))

    def addItem(self, rowIdx: int, colIdx: int, text):
        if isinstance(text, str):
            item = QtWidgets.QTableWidgetItem(text)
            self.c_tableInfo.setItem(rowIdx, colIdx, item)

    def start(self):
        index = self.c_tableInfo.currentIndex().row()
        if index < 0:
            QtWidgets.QMessageBox.information(self, '提示', '请先选中一行', QtWidgets.QMessageBox.Yes)
            return

        chaoxing.selected_course = chaoxing.courses[index]
        title = self.c_tableInfo.item(index, 1).text()

        self.c_btnStart.setEnabled(False)
        self.c_btnStart.setText(f"学习[{title}]中...")

        def __thread_download__(model: MainView, title: str):
            try:
                do_work(chaoxing)
                model.s_startEnd.emit(title, True)
            except Exception as e:
                model.s_startEnd.emit(title, False)

        _thread.start_new_thread(__thread_download__, (self, title))

    def startEnd(self, title, result):
        self.c_btnStart.setEnabled(True)
        self.c_btnStart.setText(f"开始")

        if result:
            QtWidgets.QMessageBox.information(self, '提示', f'学习[{title}]完成', QtWidgets.QMessageBox.Yes)
        else:
            QtWidgets.QMessageBox.warning(self, '提示', f'学习[{title}]失败', QtWidgets.QMessageBox.Yes)



class LoginView(QtWidgets.QWidget):
    def __init__(self, ) -> None:
        super().__init__()
        self.initView()
        self.setMinimumSize(400, 200)
        self.setWindowTitle("ChaoXing")
        self.mainView = MainView()
    
    def initView(self):
        self.c_lineUser = QtWidgets.QLineEdit()
        self.c_linePassword = QtWidgets.QLineEdit()
        self.c_btnLogin = QtWidgets.QPushButton("登录")
        self.c_btnLogin.clicked.connect(self.login)
        
        self.viewGrid = QtWidgets.QGridLayout(self)
        self.viewGrid.addWidget(QtWidgets.QLabel("账号:"), 0, 0)
        self.viewGrid.addWidget(QtWidgets.QLabel("密码:"), 1, 0)
        self.viewGrid.addWidget(self.c_lineUser, 0, 1)
        self.viewGrid.addWidget(self.c_linePassword, 1, 1)
        self.viewGrid.addWidget(self.c_btnLogin, 2, 1)
        
    def login(self):
        chaoxing.usernm = self.c_lineUser.text()
        chaoxing.passwd = self.c_linePassword.text()
        if chaoxing.login():
            self.mainView.refresh()
            self.mainView.show()
            self.hide()
        else:
            QtWidgets.QMessageBox.warning(self, '提示', f'登录失败！', QtWidgets.QMessageBox.Yes)

def main():
    app = QtWidgets.QApplication(sys.argv)
    apply_stylesheet(app, theme='dark_blue.xml')

    view = LoginView()
    view.show()

    app.exec_()


if __name__ == '__main__':
    main()
