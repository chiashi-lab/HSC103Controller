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


class DS102Controller:
    def __init__(self, ser: MySerial):
        """
        initialization
        :param ser: opened port for communication
        :type ser: MySerial
        """
        self.ser = ser
        # 送受信とスピードテーブルの確認
        for axis in ['x', 'y']:
            self.ser.send(axis2msg(axis) +'READY?')
            print(f'{axis} axis: {"READY" if self.ser.recv() == "1" else "NOT READY"}')
            if not self.speed_table_is(axis, 0):
                self.select_speed_table(axis, 0)

    def set_velocity(self, axis: str, vel: int):
        """
        set Fspeed0 vel
        :param axis: 'x' or 'y'
        :param vel: velocity you want to set
        :type axis: str
        :type vel: int
        :return:
        """
        if not 0 < vel <= 25000:
            print(f'Invalid velocity: {vel}. It must be 1~25000.')
            return

        msg = axis2msg(axis) + f'Fspeed0 {vel}'
        self.ser.send(msg)

    def set_velocity_all(self, vel: int):
        """
        set Fspeed0 vel
        :param vel: velocity you want to set
        :type vel: int
        :return:
        """
        for axis in ['x', 'y']:
            self.set_velocity(axis, vel)

    def set_velocity_max_all(self):
        """
        set Fspeed0 vel all
        :return:
        """
        self.set_velocity_all(25000)  # TODO: ほんとか？

    def select_speed_table(self, axis: str, speed: int):
        """
        select set of speed from 0~9
        :param axis: 'x' or 'y'
        :param speed: number(0~9) of the set you want to select
        :type axis: str
        :type speed: int
        :return:
        """
        msg = axis2msg(axis) + f'SELectSPeed {speed}'
        self.ser.send(msg)

    def speed_table_is(self, axis: str, speed: int) -> bool:
        """
        check the selected speed
        :param axis: 'x' or 'y'
        :param speed: number(0~9) of the set
        :type axis: str
        :type speed: int
        :rtype: bool
        :return: True or False
        """
        msg = axis2msg(axis) + 'SELectSPeed?'
        self.ser.send(msg)
        msg = self.ser.recv()
        if msg == str(speed):
            return True
        else:
            print('selected speed:', msg)
            return False

    def move_velocity(self, axis: str, vel: int):
        """
        move along selected axis with selected velocity
        :param axis: 'x' or 'y'
        :param vel: velocity
        :type axis: str
        :type vel: int
        :return:
        """
        self.set_velocity(axis, abs(vel))

        msg = axis2msg(axis) + 'GO '
        if vel > 0:
            msg += '5'
        else:
            msg += '6'
        self.ser.send(msg)

    def move_abs(self, axis: str, pos: float):
        """
        :param axis: 'x' or 'y'
        :param pos: absolute position [mm]
        :return:
        """
        msg = axis2msg(axis) + f'GOABS {pos}'
        self.ser.send(msg)

    def move_line(self, x: float, y: float):
        """
        :param x: absolute position of x [mm]
        :param y: absolute position of y [mm]
        :return:
        """
        msg = f'GOLineA X{x} Y{y}'
        self.ser.send(msg)

    def stop_axis(self, axis: str):
        """
        stop each axis
        Emergency( or Reduction)
        :param axis: 'x' or 'y'
        :type axis: str
        :return:
        """
        msg = axis2msg(axis) + 'STOP Emergency'
        # msg = axis2msg(axis) + 'STOP Reduction'
        self.ser.send(msg)

    def stop(self):
        """
        stop all
        :return:
        """
        msg = 'STOP Emergency'
        # msg = 'STOP Reduction'
        self.ser.send(msg)

    def get_position(self):
        """
        get x and y position
        the unit is mm
        :rtype (int, int)
        :return: x position, y position
        """
        # シリアル通信のエラーで稀に正しい返答が得られないことがある。プログラムが止まらないよう0を入れるようにする。
        pos = []
        for axis in ['x', 'y']:
            msg = axis2msg(axis) + 'POSition?'
            self.ser.send(msg)
            pos_axis = self.ser.recv()
            try:
                pos_axis = int(float(pos_axis) * 1000)
            except ValueError:
                pos_axis = 0
            pos.append(pos_axis)
        return pos

    def set_position(self, axis: str, pos: float):
        """
        set x and y position
        the unit is mm
        :param axis: 'x' or 'y'
        :param pos: position to set [mm]
        :return:
        """
        msg = axis2msg(axis) + f'POS {pos}'
        self.ser.send(msg)

    def check_limit(self, axis: str):
        """
        check if the current position of selected axis is on the limit
        :param axis: 'x' or 'y'
        :return: boolean
        """
        msg = axis2msg(axis) + 'LIMIT?'
        self.ser.send(msg)
        ans = int(self.ser.recv())
        if ans > 0:  # 1, 2 or 3
            return True
        return False

    def check_limit_all(self):
        """
        check if the current position is on the limit
        :param
        :return: list of boolean
        """
        return [self.check_limit('x'), self.check_limit('y')]


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
        order = 'Q:'
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
            pos_list = list(map(int, msg.split(',')))
        except ValueError:
            pos_list = [0, 0, 0]
        return pos_list

    def move_abs(self, values):
        """

        Args:
            values (list(int)): 各軸の移動量[um]を指定．

        Returns:
            bool (bool): 返答がOKならTrue．

        """

        if len(values) != 3:
            print('move value list must contain three values')
            return False

        order = 'A:' + ','.join([str(int(val * self.um_per_pulse)) for val in values])
        self.send(order)

    def move_linear(self, coord):
        """

        Args:
            coord (list(int)): 現在位置から見た終点の位置．

        Returns:
            bool (bool): 返答がOKならTrue．

        """

        if len(coord) != 3:
            print('stop list must contain [axis1(0 or 1), axis2(0 or 1), axis3(0 or 1)]')
            return False

        order = 'K:' + ','.join([str(int(val * self.um_per_pulse)) for val in [1, 2, 3] + coord])
        self.send(order)

    def jog(self, args):
        """

        Args:
            args list(int): 各軸の進行方向を1か-1で指定．動かない場合は0．

        Returns:

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

    def set_speed(self, args):
        """
        移動速度の指定．
        Args:
            args (list(int)): axis, start, final, rateを指定． axisは設定したい軸で範囲は 1~3．
            start，finalは初速度，最大速度で範囲は 1~4000000 [pulse/s] で 1 pulse あたり 0.01 μm 進む．
            rateは最大速度に到達するまでの時間で範囲は 1~1000 [ms]．

        Returns:
            bool (bool): 返答がOKならTrue．
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

    def set_speed_all(self, args):
        for i in range(1, 4):
            self.set_speed([i] + args)

    def set_speed_max(self):
        return self.set_speed_all([self.max_speed / self.um_per_pulse / 10, self.max_speed / self.um_per_pulse, 1])
