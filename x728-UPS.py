#!/usr/bin/env python3
# If power loss, it will shutdown when voltage is 3.50v.
# If power loss, it will send e-mail.
# If e-mail fails, it will wait for 10 minutes and retry.
# In order to work, you have to edit e-mail settings.

import smtplib      # For e-mail.
import ssl          # For e-mail.
import datetime     # For e-mail - day and time.
import logging      # For logfile and send PRINT output there.
import struct
import smbus
import sys
import time
import RPi.GPIO as GPIO
import os           # For 'sudo sync' command.


# Global settings:
GPIO_PORT = 26      # GPIO is 26 for x728 v2.0, GPIO is 13 for X728 v1.2 / v1.3.
I2C_ADDR = 0x36
AC_DETECT_PIN = 6   # AC Power Loss Detection GPIO Pin.
EMAIL_SEND = False  # Status of e-mail: True = SEND, False = NOT SEND.
LOG_OUTPUT = True   # Print to log file: True = LOGGING, False = Terminal.
WAITING_TIME = 0    # Waiting time if email get error.


# E-mail settings:
port = 465                    # Port.
smtp_server = "EMAIL SERVER"  # SMTP server address. 
sender_email = "YOUR EMAIL"   # Sender e-mail.
receiver_email = "TO EMAIL"   # Receiver e-mail.
password = "PASSWORD"         # Password.
subject_email = "Subject: Pi Lost Power - x728-UPS!!!"  # Your e-mail subject.
message_email = "Warning, Power is off!!!"              # Your e-mail message.


def ac_loss_callback(channel):
    global AC_ON, EMAIL_SEND, WAITING_TIME
    if GPIO.input(AC_DETECT_PIN):
        # print("Power Status: No Power")
        AC_ON = 1           # Power Lost.
        EMAIL_SEND = False  # Email not send.
    else:
        # print("Power Status: OK and Charging")
        AC_ON = 0           # AC Power OK.
        EMAIL_SEND = True   # Email was send.
        WAITING_TIME = 0    # Reset Waiting Time.


def Send_email():
    global EMAIL_SEND, P_VOLTAGE, P_CAPACITY, P_CPU_TEMP, WAITING_TIME
    try:
        now = datetime.datetime.now()
        date_time = now.strftime("%d/%m/%Y, %H:%M:%S")
        header = 'To:' + receiver_email + '\n' + 'From: ' + sender_email + '\n' + subject_email + '\n' + date_time + '\n' + P_VOLTAGE + '\n' + P_CAPACITY + '\n' + P_CPU_TEMP + '\n'
        message = header + message_email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, timeout=10, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message)
            server.quit()
            EMAIL_SEND = True
    except smtplib.SMTPException as e:
        print("E-mail Status: Error " + str(e))
        WAITING_TIME = 300  # 300*2=600, 600/60=10minutes.
        pass
    except smtplib.socket.error:
        print("E-mail Status: Error Timeout")
        WAITING_TIME = 300  # 300*2=600, 600/60=10minutes.
        pass


def readVoltage(bus):
    address = 0x36
    read = bus.read_word_data(address, 2)
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    voltage = swapped * 1.25 / 1000 / 16
    return voltage


def readCapacity(bus):
    address = 0x36
    read = bus.read_word_data(address, 4)
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    capacity = swapped / 256
    if ( capacity > 100 ):
        return 100
    else:
        return capacity


def get_temp():
    f = open("/sys/class/thermal/thermal_zone0/temp", "r")
    CPUtemp = f.read(2)
    f.close()
    try:
        # print(CPUtemp + "C")
        return int(CPUtemp)
    except (IndexError, ValueError):
        raise RuntimeError('Could not parse temperature output.')


def main():
    global AC_ON, EMAIL_SEND, P_VOLTAGE, P_CAPACITY, P_CPU_TEMP, WAITING_TIME
    if LOG_OUTPUT:
        sys.stdout = open('x728-UPS.log', 'w')  # Logfile, send all PRINT statements.
    bus = smbus.SMBus(1)     # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1).
    GPIO.setwarnings(False)  # Disable incase of relaunch.
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PORT, GPIO.OUT)
    GPIO.setup(AC_DETECT_PIN, GPIO.IN)
    GPIO.add_event_detect(AC_DETECT_PIN, GPIO.BOTH, callback=ac_loss_callback)
    AC_ON = GPIO.input(AC_DETECT_PIN)  # Get AC adapter status.
    while True:
        P_VOLTAGE = ("Voltage:%5.2fV") % readVoltage(bus)
        P_CAPACITY = ("Battery:%5i%%") % readCapacity(bus)
        P_CPU_TEMP = ("CPUTemp:   ") + format(get_temp()) + "C"
        P_AC_ON = "Error" if (AC_ON > 0) else "OK"
        if (LOG_OUTPUT == False):
            print(P_VOLTAGE, P_CAPACITY, P_CPU_TEMP, 'Power Status: ' + str(P_AC_ON), 'E-mail:  ' + str(EMAIL_SEND), 'Waiting Time:  ' + str(WAITING_TIME), sep='\t')
        if (AC_ON > 0):
            if (EMAIL_SEND == False):
                # Wait if e-mail fails.
                if (WAITING_TIME <= 0):
                    Send_email()
                else:
                    WAITING_TIME = WAITING_TIME - 1
            # Set battery low voltage to shut down.
            if readVoltage(bus) < 3.50:
                if (WAITING_TIME <= 0):
                    Send_email()
                print("Shutdown in 60 seconds...")
                time.sleep(60)
                # One final check before shutdown.
                if (AC_ON > 0):
                    os.system('sudo sync')
                    GPIO.output(GPIO_PORT, GPIO.HIGH)
                    time.sleep(3)
                    GPIO.output(GPIO_PORT, GPIO.LOW)
                else:
                    print("Power is back. Shutdown is cancel.")
        time.sleep(2)


if __name__ == "__main__":
    main()

