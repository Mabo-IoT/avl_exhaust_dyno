# -*- coding: utf-8 -*-
import time
import traceback
import struct

#import can
from simplecannet import client
import cantools

from logging import getLogger

from Doctopus.Doctopus_main import Check, Handler

log = getLogger('Doctopus.plugins')


class MyCheck(Check):
    def __init__(self, configuration):
        super(MyCheck, self).__init__(configuration=configuration)
        self.conf = configuration['user_conf']['check']
        self.init()

    def init(self):
        """
        init tcp client
        :return: 
        """
        while True:
            try:
                self.db = cantools.db.load_file(self.conf['dbc_path'])
                #self.necessary_frame_id_list = self.collect_frame_id()
                self.necessary_frame_id_list = self.conf['frame_ids']
                self.unnecessary_signals = self.conf['signals']
                self.bus = client.TcpcanBus(port=self.conf['port'], ip=self.conf['ip'])
                self.count = 0 # init count for count times of recv data
                break # only build a tcp connnection, can go to next step

            except Exception as e:
                log.error(e)
                traceback.print_exc()
                log.debug("can't init whole client")

    def collect_frame_id(self):
        """
        collect frame id list we need from dbc file
        :return:  list
        """
        messages = self.db.messages
        frame_id_list = [ frame.frame_id for frame in messages]
        return frame_id_list

    def bus_recv(self):
        """receive all data we need in the bus"""
        frames_id_list = list(self.necessary_frame_id_list)  # clone a new list
        log.debug(frames_id_list)
        data_original = []
        # collect all frames in frames_id_list
        while frames_id_list:
            frame = self.bus.recv()
            if frame:
                frame_message = self.db.decode_message(frame.arbitration_id, frame.data)
                
                if frame.arbitration_id in frames_id_list:
                    data_original.append(frame)
                    frames_id_list.remove(frame.arbitration_id)

        log.debug("receive enough frame~！！！！！！！！！！！！！！！！！！！")
        log.debug(self.necessary_frame_id_list)
        return data_original

    def dbc_convert(self, can_data):
        """
        convert can_data to right format 
        :param can_data: 
        :return: list
        """
        data_convert_dicts = {}

        for data in can_data:
            frame_message = self.db.decode_message(data.arbitration_id, data.data)
            data_convert_dicts.update(frame_message)

        if self.unnecessary_signals:
            for k in self.unnecessary_signals:
                data_convert_dicts.pop(k)    #remove unnecessary signals
        
        return data_convert_dicts

    @staticmethod
    def int_to_float(value):
        """ 
        turn int to double float
        """
        temp_value = struct.pack("I", int(value*1000))
        data = struct.unpack("i", temp_value)

        return data[0]/1000

    def format_dict(self, original_dicts):
        """
        turn data value to right type(int => float )
        :param dicts: 
        :return: dict
        """
        # data_dict = {}
        log.debug(original_dicts)
        for k, v in original_dicts.items():
            original_dicts[k] = self.int_to_float(v)
        # original_dicts['bskl_cba_ap'] /= 10

        return  original_dicts

    # def handle_warning_dict(self, data_dicts):
    #     """
    #     handle warning dict , convert to a string
    #     :param data_dicts: 
    #     :return: 
    #     """
    #     # 0: error
    #     # 1: normal
    #     # 2: don't exit
    #     warning_dicts = {
    #      'ok_gas': "气体报警;",
    #      'ok_fire': "火警报警;",
    #     }
    #     warning_string = ''
    #     warning_message = {}

    #     for k in warning_dicts.keys() & data_dicts.keys():
    #         if data_dicts[k] == 0:
    #             warning_string = warning_string + warning_dicts[k]

    #         # data_dicts.pop(k) # remove key
    #     warning_message = {'warning': warning_string }

    #     data_dicts.update(warning_message)

    #     return data_dicts
    
    @staticmethod
    def handle_puma_code(puma_status_code):
        """
        parse puma_status_code to status
        2: monitor 
        5: mannual
        6: automatic

        automatic: status = 1
        mannaul/monitor: status = 0

        """
        if puma_status_code == 6:
            return 1
        else:
            return 0

    @staticmethod
    def handle_dyno_mode(dyno_mdoe_code):
        """
        parse dyno mode code to dyno status
        100: STBY  status = 0
        0: STOP status = 0
        2: RUN status = 1
        """
        if dyno_mdoe_code == 2:
            return 1
        else: 
            return 0

    @staticmethod
    def handle_dyno_direction(dyno_direction_code):
        """
        parse dyno_direction_code to direction
        200: forward
        100: backward
        0:no direction
        """
        direction_dicts = {
            200: "forward",
            100: "backward",
            0: "no direction",
        }

        direction = direction_dicts.get(dyno_direction_code, "no direction")
        return direction

    def handle_dict(self, data_dicts):
        """
        
        :param data_dicts: original data dicts
        :return: handled data_dicts
        """
        
        puma_status_number = data_dicts['status']
        dyno_mode_code = data_dicts['mode']
        dyno_direction_code = data_dicts['direction']

        data_dicts['status'] = self.handle_puma_code(puma_status_number)
        data_dicts['mode'] =  self.handle_dyno_mode(dyno_mode_code)
        data_dicts['direction'] = self.handle_dyno_direction(dyno_direction_code)

        return data_dicts

    def reconnect(self):
        """
        reconnect to tcp_can
        :return: 
        """
        self.bus.reconnect()

    def user_check(self):
        """

        :param command: user defined parameter.
        :return: the data you requested.
        """
        log.debug("begin~~~~~~~~~~~~~~~~~~~~~~!!!!!!!!!!!!!!!!")
        # trying recv data:
        try:
            # time.sleep(1)
            # when self. count=10, send data to low 10Hz to 1Hz
            
            # recv
            data_original = self.bus_recv()

            data_convert_dicts = self.dbc_convert(data_original)

            data_dicts = self.format_dict(data_convert_dicts)

            data_dicts_handle = self.handle_dict(data_dicts)

            # final_data_dicts = self.handle_warning_dict(data_dicts_handle)
            #final_data_dicts = data_dicts_handle

            log.debug('data dict is {}'.format(data_dicts_handle))
            
            if self.count >= 10:
                self.count = 0
                yield data_dicts_handle
            else:
                self.count = self.count + 1

        except Exception as e:
            log.error(e)
            traceback.print_exc()
            self.reconnect()


class MyHandler(Handler):
    def __init__(self, configuration):
        super(MyHandler, self).__init__(configuration=configuration)
        self.exhaust_conf = configuration['user_conf']['handler']['exhaust']
        self.dyno_conf = configuration['user_conf']['handler']['dyno']

    def user_handle(self, raw_data):
        """
        用户须输出一个dict，可以填写一下键值，也可以不填写
        timestamp， 从数据中处理得到的时间戳（整形?）
        tags, 根据数据得到的tag
        data_value 数据拼接形成的 list 或者 dict，如果为 list，则上层框架
         对 list 与 field_name_list 自动组合；如果为 dict，则不处理，认为该数据
         已经指定表名
        measurement 根据数据类型得到的 influxdb表名

        e.g:
        list:
        {'data_value':[list] , required
        'tags':[dict],        optional
        'table_name',[str]   optional
        'timestamp',int}      optional

        dict：
        {'data_value':{'fieldname': value} , required
        'tags':[dict],        optional
        'table_name',[str]   optional
        'timestamp',int}      optional

        :param raw_data: 
        :return: 
        """
        # exmple.
        # 数据经过处理之后生成 value_list
        data_value_list = raw_data
        
        exhuast_dict, dyno_dict = self.separate_dict(data_value_list)

        # user 可以在handle里自己按数据格式制定tags
        exhuast_dict_handle = self.re_format_exhaust_dict(exhuast_dict)

        user_postprocessed = {
            'data_value': exhuast_dict_handle,
            'table_name': self.exhaust_conf['table_name'],
            'tags': self.exhaust_conf['tags'],
        }

        yield user_postprocessed

        dyno_dict_handle = self.re_format_dyno_dict(dyno_dict)

        user_postprocessed = {
            'data_value': dyno_dict_handle,
            'table_name': self.dyno_conf['table_name'],
            'tags': self.dyno_conf['tags'],
        }

        yield user_postprocessed

    @staticmethod
    def separate_dict(data_dict):
        """
        separate exhaust and dyno dict from data_dict
        """
        exhaust_keys = ["SN_Conc_COL_Diluted", "SN_Conc_CO2_Diluted", "SN_Conc_HC_Diluted", "SN_Conc_CH4_Diluted",
                        "SN_Conc_NOX_Diluted", "SN_Conc_N2O_Diluted", "SN_Conc_Particulnteg_DilutedAPC",
                        "SN_Q_CVS", "SN_P_CVS", "SN_T_CVS", "status"]

        dyno_keys = ["grade", "weight", "F0", "F1", "F2", "f0", "f1", "f2", "actural_speed", "actural_tractive_force",
                     "warning", "warning_string1", "warning_string2", "warning_string3", "warning_string4",
                     "warning_string5", "warning_string6", "warning_string7", "warning_string8", "warning_string9",
                     "warning_string10", "mode", "direction"]
        
        exhaust_dict = {}
        dyno_dict = {}

        for exhaust_key in exhaust_keys:
            exhaust_dict.update(data_dict[exhaust_key])
        
        for dyno_key in dyno_keys:
            dyno_dict.update(data_dict[dyno_key])
        
        return exhaust_dict, dyno_dict

    @staticmethod
    def re_format_dyno_dict(dyno_dict):
        """
        re_format dyno_dict change "mode" to "status" 
        adapt in influxdb data fields format
        """
        dyno_dict["status"] = dyno_dict.pop("mode")

        return dyno_dict

    @staticmethod
    def re_format_exhaust_dict(exhaust_dict):
        """
        re_format exhaust dict
        adapt in influxdb data fields format
        """

        return exhaust_dict





            
