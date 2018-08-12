# sudo apt install swig wiringpi
# pip install -U wiringpi spidev

import wiringpi
import time
import spidev
import sys
import array
import logging
from functools import reduce


SPI_CE1_PIN = 10
SPI_CE0_PIN = 11
CPU_BOOT0_PIN = 5
CPU_NRST_PIN = 4
FLASH_ADDRESS = (0x08000000, 0x08080000)

ACK = 0x79
NACK = 0x1F


logger = logging.getLogger()
spi = spidev.SpiDev()


def spi_xfer(data):
    return spi.xfer2(data, 500000, 500)


def bootloader_init():
    # Initialize SPI and GPIOs
    wiringpi.wiringPiSetup()
    spi.open(0, 0)
    wiringpi.pinMode(SPI_CE0_PIN, 1)
    wiringpi.pinMode(SPI_CE1_PIN, 1)
    wiringpi.pinMode(CPU_BOOT0_PIN, 1)
    wiringpi.pinMode(CPU_NRST_PIN, 1)

    # Bootloader activation
    # Source: STM32 microcontroller system memory boot mode (p. 20, p. 279)
    logger.info('Activating bootloader...')
    wiringpi.digitalWrite(CPU_NRST_PIN, 0)
    wiringpi.digitalWrite(SPI_CE0_PIN, 1)
    wiringpi.digitalWrite(SPI_CE1_PIN, 1)
    wiringpi.digitalWrite(CPU_BOOT0_PIN, 1)
    time.sleep(0.5)
    wiringpi.digitalWrite(CPU_NRST_PIN, 1)
    time.sleep(0.5)
    
    # Bootloader SPI synchronization frame
    # Source: SPI protocol used in the STM32 bootloader (p. 6)
    logger.info('Syncing SPI...')
    recv = spi_xfer([0x5A])
    logger.debug('Received %s' % recv)
    recv = spi_xfer([0x00])
    logger.debug('Received %s' % recv)
    recv = spi_xfer(recv)
    logger.debug('Received %s' % recv)
    if recv[0] != ACK:
        raise Exception('ACK not received')


def bootloader_write(data, start_address=FLASH_ADDRESS[0]):
    """
    Source: SPI protocol used in the STM32 bootloader (p. 20)
    """
    # Send command
    logger.info('Writting data to MCU...')
    recv = spi_xfer([0x5A, 0x31, 0xCE])
    logger.debug('Received %s' % recv)
    #recv = spi_xfer([0x00, 0x00, 0x79])
    #logger.debug('Received %s' % recv)

    # Send start address
    start_bytes = [
        (start_address >> 24) & 0xFF,
        (start_address >> 16) & 0xFF,
        (start_address >> 8) & 0xFF,
        (start_address >> 0) & 0xFF
    ]
    start_checksum = start_bytes[0] ^ \
        start_bytes[1] ^ \
        start_bytes[2] ^ \
        start_bytes[3]
    recv = spi_xfer(start_bytes + [start_checksum])
    logger.debug('Received %s' % recv)

    # Send number of bytes + data + checksum
    if len(data) % 2 == 1:
      data += [ 0xFF ]
    cs = reduce((lambda x, y: x ^ y), [ len(data) ] + data, 0)
    recv = spi_xfer([ len(data) ] + data + [cs])
    logger.debug('Received %s' % recv)


def main():
    # Configure logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(message)s'))
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    bootloader_init()

    with open('./blink.bin', 'rb') as f:
        start_address = FLASH_ADDRESS[0]
        while True:
            bytes_chunk = f.read(256)
            if not bytes_chunk:
                break
            else:
                bootloader_write(bytes_chunk, start_address)
                start_address += 256

main()