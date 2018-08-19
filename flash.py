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
SYNC_BYTE = 0x5A
SYNC_BYTE_RESP = 0xA5


logger = logging.getLogger()
spi = spidev.SpiDev()


def spi_xfer(data):
    return spi.xfer2(data, 500000, 50)


def ack():
    logger.debug('ACK: Starting...')
    recv = spi_xfer([0x00])
    while True:
        recv = spi_xfer([0x00])
        logger.debug('ACK: Received %s' % hex(recv[0]))
        if recv[0] == NACK:
            raise Exception('NACK received')
        elif recv[0] == ACK:
            return
        else:
            #raise Exception('Garbage received')
            time.sleep(0.1)
            # return
    spi_xfer([0x79])


def sync_frame():
    logger.info('Syncing SPI...')
    recv = spi_xfer([SYNC_BYTE])
    if recv[0] != SYNC_BYTE_RESP:
        raise Exception('Sync byte response not correct')
        
    logger.debug('ACK: Starting...')
    recv = spi_xfer([0x00])
    logger.debug('ACK: Dummy byte received %s' % hex(recv[0]))
    recv = spi_xfer(recv)
    logger.debug('ACK: Received %s' % hex(recv[0]))
    if recv[0] == NACK:
        raise Exception('NACK received')
    if recv[0] != ACK:
        raise Exception('Garbage received')
    #recv = spi_xfer([ACK])


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
    # sync_frame()


def bootloader_write(data, start_address=FLASH_ADDRESS[0]):
    """
    Source: SPI protocol used in the STM32 bootloader (p. 20)
    """
    # Send command
    logger.info('Writting data to MCU...')
    recv = spi_xfer([0x5A, 0x31, 0xCE])
    print(recv)
    if recv[2] != ACK:
        raise('ACK not received')
    ack()

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
    spi.writebytes(start_bytes + [start_checksum])
    #logger.debug('Received %s' % map(hex, recv))
    ack()

    # Send number of bytes + data + checksum
    time.sleep(0.01)
    if len(data) % 2 == 1:
      data += [ 0xFF ]
    cs = reduce((lambda x, y: x ^ y), [ len(data) - 1] + data, 0)
    spi.writebytes([ len(data) -1 ] + data + [cs])
    ack()


def main():
    # Configure logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(message)s'))
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    bootloader_init()
    sync_frame()
    with open('./blink.bin', 'rb') as f:
        start_address = FLASH_ADDRESS[0]
        while True:
            bytes_chunk = map(ord, f.read(256))
            if not bytes_chunk:
                break
            else:
                while True:
                    
                    try:
                        logger.info("Writing from %s to %s" % 
                            (hex(start_address), hex(start_address + len(bytes_chunk)))
                        )
                        bootloader_write(bytes_chunk, start_address)
                        break
                    except Exception as e:
                        raise
                        logger.warning('Repeating transaction...')

                start_address += 256

main()