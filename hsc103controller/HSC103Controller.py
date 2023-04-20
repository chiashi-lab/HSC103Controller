import serial


class MySerial(serial.Serial):
    # serial.SerialではEOLが\nに設定されており、DS102の規格と異なる
    eol = b'\r'
    leneol = len(eol)

    def __init__(self, port, baudrate, **args):
        super().__init__(port, baudrate, **args)

    def send(self, msg: str):
        msg = msg.encode() + self.eol
        self.write(msg)

    def recv(self):
        line = bytearray()
        while True:
            c = self.read(1)
            if c:
                line += c
                if line[-self.leneol:] == self.eol:
                    break
            else:
                break
        return bytes(line).decode().strip('\r')


def axis2msg(axis: str):
    """
    convert axis to 'AXIs<axis>:'
    :param axis: 'x' or 'y'
    :type axis: str
    :rtype: str
    :return: message string
    """
    if axis not in ['x', 'y']:
        raise ValueError('Axis must be x or y.')
    msg = 'AXIs'
    if axis == 'x':
        msg += '1'
    elif axis == 'y':
        msg += '2'
    msg += ':'
    return msg


class HSC103Controller:
    def __init__(self, ser=None):
        self.ser = ser
        self.end = '\r\n'

        self.um_per_pulse = 0.01
        self.max_speed = 4000000 * self.um_per_pulse  # [um]

        self.check_status()

    def send(self, order: str):
        if self.ser is None:
            return
        order += self.end
        self.ser.write(order.encode())

    def recv(self) -> str:
        if self.ser is None:
            return 'some response'
        msg = self.ser.readline().decode()
        msg.strip(self.end)
        return msg

    def check_status(self):
        msg = '!:'
        self.send(msg)
        print(msg, self.recv())
        for command in ['N', 'V', 'P']:
            msg = f'?:{command}'
            self.send(msg)
            print(msg, self.recv())
        for i, axis in enumerate(['x', 'y', 'z']):
            print()
            print(axis)
            for command in ['D', 'B']:
                msg = f'?:{command}{i + 1}'
                self.send(msg)
                print(msg, self.recv())

    def is_busy(self):
        order = '!:'
        self.send(order)
        msg = self.recv()
        try:
            busy_list = list(map(int, msg.split(',')))  # 1: busy, 0: ready
        except ValueError:
            busy_list = [-1, -1, -1]
        return busy_list

    def get_position(self):
        order = 'Q:'
        self.send(order)
        msg = self.recv()
        try:
            pos_list = list(map(lambda x: int(x) * self.um_per_pulse, msg.split(',')))
        except ValueError:
            print(msg)
            pos_list = [0, 0, 0]
        return pos_list

    def move_abs(self, values: list):
        if len(values) != 3:
            print('move value list must contain three values')
            return False

        order = 'A:' + ','.join([str(int(val / self.um_per_pulse)) for val in values])
        self.send(order)

    def move_linear(self, coord: list):
        if len(coord) != 3:
            print('stop list must contain [axis1(0 or 1), axis2(0 or 1), axis3(0 or 1)]')
            return False

        order = 'K:1,2,3,' + ','.join([str(int(val / self.um_per_pulse)) for val in coord])
        self.send(order)

    def jog(self, args: list):
        """

        Args:
            args list(int): 各軸の進行方向を1か-1で指定．動かない場合は0．

        """

        if len(args) != 3:
            print('jog list must contain [axis1(0 or 1), axis2(0 or 1), axis3(0 or 1)]')
            return False
        if args[0] not in [-1, 0, 1] or args[1] not in [-1, 0, 1] or args[2] not in [-1, 0, 1]:
            print('jog value must be -1 ~ 1')
            return False

        order = 'J:'
        for s in args:
            if s == -1:
                order += '-,'
            elif s == 0:
                order += ','
            elif s == 1:
                order += '+,'
        order = order[:-1]
        self.send(order)

    def stop_emergency(self):
        order = 'L:E'
        self.send(order)

    def set_speed(self, args: list):
        """
        移動速度の指定．
        Args:
            args (list(int)): axis, start, final, rateを指定． axisは設定したい軸で範囲は 1~3．
            start，finalは初速度，最大速度で範囲は 1~4000000 [pulse/s] で 1 pulse あたり 0.01 μm 進む．
            rateは最大速度に到達するまでの時間で範囲は 1~1000 [ms]．

        """

        if len(args) != 4:
            print('speed list must contain [axis(1~3), start(1~4000000), final(1~4000000), rate(1~1000)]')
            return False

        axis, start, final, rate = args

        if axis not in [1, 2, 3]:
            print('axis number must be 1 ~ 3')
            return False
        if start < 1 or self.max_speed / self.um_per_pulse < start \
                or final < 1 or self.max_speed / self.um_per_pulse < final or final < start \
                or rate < 1 or 1000 < rate:
            print('speed value out of range.\n1<=slow<=fast<=4000000, 1<=rate<=1000.')
            return False

        order = 'D:' + ','.join([str(int(val)) for val in args])
        self.send(order)

    def set_speed_all(self, args: list):
        for i in range(1, 4):
            self.set_speed([i] + args)

    def set_speed_max(self):
        return self.set_speed_all([self.max_speed / self.um_per_pulse / 10, self.max_speed / self.um_per_pulse, 1])
