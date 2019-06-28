#!/usr/bin/python2.7
# -*- coding:utf-8 -*-
#
#  Environmental Measurement IoT device:
#  use :BME280 sensor on I2C bus
#       soracom air SIM and Ak-020 Dongle
#       soracom harvest service, and it better to have Lagoon service.
#
#  send environmental data [temperture, humidity, pressure] every 20s
#   format: {"temp":21.9,"humid":46.5,"atmPressure":1007.4}
#

import socket
from contextlib import closing

from smbus import SMBus
import ADS
import bme280

import os
import commands
import time
import logging

import json

# logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# create a file handler
handler = logging.FileHandler('/var/log/soracom.log')
handler.setLevel(logging.WARNING)

# create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(handler)


def soraSend(hostName,portNumber,payload):
    soracom = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with closing(soracom):    # サーバを指定
        soracom.connect((hostName, portNumber))
    # サーバにメッセージを送る
        soracom.sendall(payload)
    # ネットワークのバッファサイズは1024。サーバからの文字列を取得する
        ret=soracom.recv(1024)
        logger.info('sent data')
    return ret
    #print(soracom.recv(1024))

#  constants for connecting to the service
hostName='harvest.soracom.io'
portNumber=8514
resultSend=''

# constants for I2C device
bus_number  = 1
bme280_address = 0x76
ADS_address = 0x48

# make I2C bus instance
bus = SMBus(bus_number)

if __name__ == '__main__':

    logger.warning('Start script: %s', __file__)


    foundADS1115 = ADS.init(bus, ADS_address)
    if not(foundADS1115) :
        logger.warning('!! Found No ADS1115 on Address {0:x}'.format(ADS_address))

    foundBME280 = bme280.setup(bus,bme280_address)
    if not(foundBME280) :
        logger.warning('!! Found No BME280 on Address {0:x}'.format(bme280_address))

# ADC1115 configuration
    if foundADS1115 :
        ADC_config = ADS._CONFIG_DEFAULT & (~ ADS._MASK_RATE) | ADS._CONFIG_RATE['8SPS']
        ADC_config = ADC_config & (~ ADS._MASK_RANGE) | ADS._CONFIG_RANGE['4V']
        dummy = ADS.setCondition(bus, ADS_address, ADC_config)
        logger.info('> {0:x}'.format(ADC_config))

# mesurement cycle in sec
    interval = 18.5

    while True:

        measurements={}

        ADSdata=[32767,32767]
        if foundADS1115 :
            try:
                ADSdata = ADS.readoutMulti(bus, ADS_address, ['01','23'])
            except IOError as msg:
                logger.warning('ADS did not respond: %s',msg)
            except :
                logger.warning('Something happed on I2C bus')
        # readout in [V]
        readOutInVolt = [ADSdata[0]/32767.*4.096*4., ADSdata[1]/32767.*4.096*2.]
        # print ADSdata

        # convert to actual unit of the each sensor
        # condition:
        #   analog output of the Panel Meter was set to 2.5V=100%
        # unit = [ % , kPa]
        correctedReadOut =[readOutInVolt [0] * 4 * 10, (readOutInVolt [1]-1) / 4 * 100]

        measurements["level"]    = correctedReadOut[0]
        measurements["pressure"] = correctedReadOut[1]

        environmentalData = [0,0,0]

        if foundBME280 :
            try:
                environmentalData = bme280.readData(bus, bme280_address)
            except  IOError as msg:
                logger.warning('BME280 did not respond: %s',msg)
            except :
                logger.warning('Somthing happend on I2C bus')

        measurements["temp"]        = environmentalData[0]
        measurements["humid"]       = environmentalData[2]
        measurements["atmPressure"] = environmentalData[1]

        #payload = '\"temp\":{0[0]:.3f} ,\"humid\":{0[2]:.3f} ,\"atmPressure\":{0[1]:.2f}'.format(environmentalData)
        #payload = payload + ', \"level\":{0[0]:2.5f} ,\"pressure\":{0[1]:2.5f} '.format(ADSdata)
        #payload += ', \"level\":{0[0]:4.2f} ,\"pressure\":{0[1]:4.2f} '.format(correctedReadOut)

        #payload = "{" + payload + "}"

        payload = json.dumps(measurements)

        logger.debug('%f - %s', time.time(),payload)

        try:
            resultSend = soraSend(hostName,portNumber,payload)
            logger.info('Result: %s', resultSend)
        except socket.gaierror as msg:
#            print("send error !")
            logger.warning('Error on sending data: %s',msg)
        except :
            logger.warning('unexpected errror occurred.')

        time.sleep(interval)
