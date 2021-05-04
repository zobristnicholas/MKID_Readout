from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *
import collections

from analogreadout.external.lakeshore370ac.driver import (
    Command, Driver, CommandSequence)
from analogreadout.external.lakeshore370ac.iec60488 import IEC60488
from analogreadout.external.lakeshore370ac.types import (
    Boolean, Enum, Float, Integer, Register, String)
from analogreadout.external.lakeshore370ac import misc


class Curve(Driver):
    """A LS370 curve.

    :param transport: A transport object.
    :param protocol: A protocol object.
    :param idx: The curve index.
    :param length: The curve buffer length.

    :ivar header: The curve header configuration.
        *(<name><serial><format><limit><coefficient>)*, where

        * *<name>* The name of the curve, a string limited to 15 characters.
        * *<serial>* The serial number, a string limited to 10 characters.
        * *<format>* Specifies the curve data format. Valid entries are
          'Ohm/K' and 'logOhm/K'.
        * *<limit>* The curve temperature limit in Kelvin.
        * *<coefficient>* The curves temperature coefficient. Valid entries are
          `'negative'` and `'positive'`.

    The Curve is implementing the `collections.sequence` protocoll. It models a
    sequence of points. These are tuples with the following structure
    *(<units value>, <temp value>)*, where

    * *<units value>* specifies the sensor units for this point.
    * *<temp value>* specifies the corresponding temperature in kelvin.

    To access the points of this curve, use indexing and slicing operations,
    e.g.::

        # assuming an LS30 instance named ls30, the following will print the
        # sixth point of the first user curve.
        curve = ls370.user_curve[0]
        print curve[1]   # print second point
        print curve[-1]  # print last point
        print curve[::2] # print every second point

        # Set the fifth data point to 0.10191 sensor units and 470.000 K.
        curve[5] = 0.10191, 470.000

    .. note::

        Be aware that the builtin :func:`len()` function returns the buffer
        length, **not** the number of points.

    .. warning ::

        In contrast to the LS370 device, point indices start at 0 **not** 1.

    """
    def __init__(self, transport, protocol, idx, length):
        super(Curve, self).__init__(transport, protocol)
        self.idx = idx = int(idx)
        self.header = Command(
            'CRVHDR? {0}'.format(idx),
            'CRVHDR {0},'.format(idx),
            [
                String(max=15),
                String(max=10),
                Enum('Ohm/K', 'logOhm/K', start=3),
                Float(min=0.),Enum('negative', 'positive', start=1)
            ]
        )
        if length > 0:
            self.__length = int(length)
        else:
            raise ValueError('length must be a positive integer > 0')

    def __len__(self):
        """The length of the curve buffer **not** the number of points."""
        return self.__length

    def __getitem__(self, item):
        if isinstance(item, slice):
            indices = item.indices(len(self))
            return [self[i] for i in range(*indices)]
        # Simple index
        item = misc.index(item, len(self))
        # construct command
        response_t = [Float, Float]
        data_t = [Integer(min=1), Integer(min=1, max=200)]
        # Since indices in LS304 start at 1, it must be added.
        return self._query(('CRVPT?', response_t, data_t), self.idx, item + 1)

    def __setitem__(self, item, value):
        if isinstance(item, slice):
            indices = item.indices(min(len(self), len(value)))
            for i in range(*indices):
                self[i] = value[i]
        else:
            item = misc.index(item, len(self))
            unit, temp = value
            data_t = [Integer(min=1), Integer(min=1, max=200), Float, Float]
            # Since indices in LS304 start at 1, it must be added.
            self._write(('CRVPT', data_t), self.idx, item + 1, unit, temp)

    def delete(self):
        """Deletes this curve."""
        self._write(('CRVDEL', Integer), self.idx)


class Display(Driver):
    """A LS370 Display at the chosen location.

    :param transport: A transport object.
    :param protocol: A protocol object.
    :param location: The display location.

    :ivar config: The configuration of the display.
        *(<channel>, <source>, <resolution>)*, where

        * *<channel>* The index of the displayed channel, 0-16, where 0
          activates channel scanning.
        * *<source>* The displayed data. Valid entries are 'kelvin', 'ohm',
          'linear', 'min' and 'max'
        * *<resolution>* The displayed resolution in number of digits, 4-6.

    """

    def __init__(self, transport, protocol, location):
        super(Display, self).__init__(transport, protocol)
        location = int(location)
        self.config = Command(
            'DISPLOC? {0}'.format(location),
            'DISPLOC {0},'.format(location),
            [
                Integer(min=0, max=16),
                Enum('kelvin', 'ohm', 'linear', 'min', 'max', start=1),
                Integer(min=4, max=6)
            ]
        )


class Heater(Driver):
    """An LS370 Heater.

    :param transport: A transport object.
    :param protocol: A protocol object.

    :ivar manual_output: The manual heater output, a float representing the
        percent of current or actual power depending on the heater output
        selection.
    :ivar output: The heater output in percent of current or actual power
        dependant on the heater output selection.
    :ivar range: The heater current range. Valid entries are 'off',
        '31.6 uA', '100 uA', '316 uA', '1 mA', '3.16 mA', '10 mA', '31.6 mA',
        and '100 mA'
    :ivar status: The heater status, either 'no error' or 'heater open error'.

    """
    #: The supported heater ranges.
    RANGE = [
        'off', '31.6 uA', '100 uA', '316 uA', '1 mA',
        '3.16 mA', '10 mA', '31.6 mA', '100 mA'
    ]

    def __init__(self, transport, protocol):
        super(Heater, self).__init__(transport, protocol)
        self.manual_output = Command('MOUT?', 'MOUT', Float)
        self.output = Command(('HTR?', Float))
        self.range = Command(
            'HTRRNG?',
            'HTRRNG',
            Enum('off', '31.6 uA', '100 uA', '316 uA', '1 mA',
                 '3.16 mA', '10 mA', '31.6 mA', '100 mA')
        )
        self.status = Command(
            ('HTRST?', Enum('no error', 'heater open error'))
        )


class Input(Driver, collections.Sequence):
    """The LS370 Input.

    :param transport: A transport object.
    :param protocol: A protocol object.

    :ivar scan:

    It is a sequence like interface to each :class:`~.InputChannel`.

    E.g. to access the kelvin reading of channel 5, Assuming an instance of :class:`~.LS370` named
    `ls370`, one would simply write.::

        >>> ls370.input[5].kelvin

    To scan the second channel, and activate the autoscan one would write::

        >>> ls370.input.scan = 2, True

    .. note::

        In contrast to the LS370 internal commands the channel indexing is zero
        based.

    """
    def __init__(self, transport, protocol, channels):
        super(Input, self).__init__(transport, protocol)
        # The ls370 channels start at 1
        self._channels = tuple(
            InputChannel(transport, protocol, idx) for idx in range(1, channels + 1)
        )
        self.scan = Command(
            'SCAN?',
            'SCAN',
            (Integer(min=0, max=len(self)), Boolean)
        )

    def __len__(self):
        return len(self._channels)

    def __getitem__(self, channel):
        return self._channels[channel]


class InputChannel(Driver):
    """A LS370 input channel.

    :param transport: A transport object.
    :param protocol: A protocol object.
    :param idx: The channel index.

    :ivar alarm: The alarm configuration.
        *(<enabled>, <source>, <high>, <low>, <deadband>, <latch>)*, where

        * *<enable>* enables/disables the alarm, valid are `True`, `False`.
        * *<source>* The data channel against which the alarm condition is
          checked. Either 'kelvin', 'ohm' or 'linear'.
        * *<high>* The high alarm value.
        * *<low>* The low alarm value.
        * *<deadband>* The value the source value must change to deactivate
          the non-latched alarm.
        * *<latch>* Enables/disables the latched alarm. (A latched alarm stays
          active, even if the alarm condition isn't met anymore).

    :ivar alarm_status: The status of the high and low alarm.
        *(<high state>, <low state>)*, where

        * *<high state>* is either `True`or `False`.
        * *<low state>* is either `True`or `False`.

    :ivar config: The input channel configuration.
        *(<enabled>, <dwell>, <pause>, <curve>, <coefficient>)*, where

        * *<enabled>* enables/disables the channel, valid are `True`, `False`.
        * *<dwell>* The autoscanning dwell time in seconds, 1-200.
        * *<pause>* The change pause time in seconds, 3-200.
        * *<curve>* The curve used by the channel, valid are 'no curve' or
          0-19 the index of the user curves.
        * *<coefficient>* The temperature coefficient used if no curve is
          selected. Valid are 'negative' and 'positive'.

    :ivar excitation_power: The current excitation power.
    :ivar filter: The filter parameters.
        *(<enabled>, <settle time>, <window>)*, where

        * *<enabled>* A boolean enabling/disabling the filtering.
        * *<settle time>* The settle time in seconds, 1-200.
        * *<window>* The filtering window, 1-80 in precent of the fullscale
          reading.

    :ivar index: The index of the input channel.
    :ivar kelvin: The input channel reading in kelvin.

        .. note:: If no curve is present, the reading will be `0.`.

    :ivar linear: Linear equation data.
    :ivar linear_equation: The input linear equation parameters.
        *(<equation>, <m>, <x source>, <b source>, <b>)*, where

         * *<equation>* is either `'slope-intercept'` or `'point-slope'`,
           meaning 'y = mx + b' or 'y = m(x + b)'.
         * *<m>* The slope.
         * *<x source>* The input data to use, either 'kelvin', 'celsius' or
           'sensor units'.
         * *<b source>* Either 'value', '+sp1', '-sp1', '+sp2' or '-sp2'.
         * *<b>* The b value if *<b source>* is set to 'value'.

    :ivar minmax: The min max data, *(<min>, <max>)*, where

         * *<min>* Is the minimum input data.
         * *<max>* Is the maximum input data.

    :ivar minmax_param: Configures the source data to use with the minmax
        filter. Valid are 'kelvin', 'ohm' and 'linear'.
    :ivar reading_status: The channel reading status. A register with the
        following keys

        * 'cs overload' Current source overload.
        * 'vcm overload' Common mode voltage overload.
        * 'vmix overload' Mixer overload.
        * 'vdif overload' Differential overload.
        * 'range over' The selected resistance range is too low.
        * 'range under' The the polarity (+/-) of the current or voltage
          leads is wrong and the selected resistance range is too low.

    :ivar resistance: The input reading in ohm.
    :ivar resistance_range: The resistance range configuration.
        *(<mode>, <excitation>, <range>, <autorange>, <excitation_enabled>)*

        * *<mode>* The excitation mode, either 'current' or 'voltage'.
        * *<excitation>* The excitation range, either 1-22 for current
          excitation or 1-12 for voltage excitation.

    """
    def __init__(self, transport, protocol, idx):
        super(InputChannel, self).__init__(transport, protocol)
        self.index = idx = int(idx)
        self.alarm = Command(
            'ALARM ? {0}'.format(idx),
            'ALARM {0},'.format(idx),
            [Boolean, Enum('kelvin', 'ohm', 'linear'),
             Float, Float, Float, Boolean]
        )
        self.alarm_status = Command(
            ('ALARMST? {0}'.format(idx), [Boolean, Boolean])
        )
        self.autoscan = Command(
            'SCAN? {0}'.format(idx),
            'SCAN {0},'.format(idx),
            Boolean
        )
        self.config = Command(
            'INSET? {0}'.format(idx),
            'INSET {0},'.format(idx),
            [
                Boolean, Integer(min=1, max=200),
                Integer(min=3, max=200),
                Enum('no curve', *range(20)),
                Enum('negative', 'positive', start=1)
            ]
        )
        self.excitation_power = Command(('RDGPWR? {0}'.format(idx), Float))
        self.filter = Command(
            'FILTER? {0}'.format(idx),
            'FILTER {0},'.format(idx),
            [Boolean, Integer(min=1, max=200), Integer(min=1, max=80)]
        )
        self.kelvin = Command(('RDGK? {0}'.format(idx), Float))
        self.linear = Command(('LDAT? {0}'.format(idx), Float))
        self.linear_equation = Command(
            'LINEAR? {0}'.format(idx),
            'LINEAR {0},'.format(idx),
            [
                Enum('slope-intercept', 'point-slope'),
                Float,  # m value
                Enum('kelvin', 'celsius', 'sensor units', start=1),
                Enum('value', '+sp1', '-sp1', '+sp2', '-sp2', start=1),
                Float,  # b value
            ]
        )
        self.minmax = Command(('MDAT? {0}'.format(idx), [Float, Float]))
        self.minmax_parameter = Command(
            'MNMX? {0}'.format(idx),
            'MNMX {0},'.format(idx),
            Enum('kelvin', 'ohm', 'linear'),
        )
        self.reading_status = Command((
            'RDGST? {0}'.format(idx),
            Register({
                0: 'cs overload',  # current source overload
                1: 'vcm overload',  # voltage common mode overload
                2: 'vmix overload',  # differential overload
                3: 'vdif overload',  # mixer overload
                4: 'range over',
                5: 'range under',
                6: 'temp over',
                7: 'temp under',
            })
        ))
        self.resistance = Command(('RDGR? {}'.format(idx), Float))
        self.resistance_range = Command(
            'RDGRNG? {0}'.format(idx),
            'RDGRNG {0},'.format(idx),
            [
                Enum('voltage', 'current'),
                Integer(min=1, max=22),
                Integer(min=1, max=22),
                Boolean,
                Boolean
            ]
        )


class Output(Driver):
    """Represents a LS370 analog output.

    :param transport: A transport object.
    :param protocol: A protocol object.
    :param channel: The analog output channel. Valid are either 1 or 2.

    :ivar analog: The analog output parameters, represented by the tuple
        *(<bipolar>, <mode>, <input>, <source>, <high>, <low>, <manual>)*,
        where:

         * *<bipolar>* Enables bipolar output.
         * *<mode>* Valid entries are 'off', 'channel', 'manual', 'zone',
            'still'. 'still' is only valid for the output channel 2.
         * *<input>* Selects the input to monitor (Has no effect if mode is
           not `'input'`).
         * *<source>* Selects the input data, either 'kelvin', 'ohm', 'linear'.
         * *<high>* Represents the data value at which 100% is reached.
         * *<low>* Represents the data value at which the minimum value is
           reached (-100% for bipolar, 0% otherwise).
         * *<manual>* Represents the data value of the analog output in manual
           mode.
    :ivar value: The value of the analog output.

    """
    def __init__(self, transport, protocol, channel):
        super(Output, self).__init__(transport, protocol)
        if not channel in (1, 2):
            raise ValueError('Invalid Channel number. Valid are either 1 or 2')
        self.channel = channel
        mode = 'off', 'channel', 'manual', 'zone'
        mode = mode + ('still',) if channel == 2 else mode
        self.analog = Command('ANALOG? {0}'.format(channel),
                              'ANALOG {0},'.format(channel),
                              [Enum('unipolar', 'bipolar'),
                               Enum(*mode),
                               Enum('kelvin', 'ohm', 'linear', start=1),
                               Float, Float, Float])
        self.value = Command(('AOUT? {0}'.format(channel), Float))


class Relay(Driver):
    """A LS370 relay.

    :param transport: A transport object.
    :param protocol: A protocol object.
    :param idx: The relay index.

    :ivar config: The relay configuration.
        *(<mode>, <channel>, <alarm>)*, where

        * *<mode>* The relay mode either 'off' 'on', 'alarm' or 'zone'.
        * *<channel>* Specifies the channel, which alarm triggers the relay.
            Valid entries are 'scan' or an integer in the range 1-16.
        * *<alarm>* The alarm type triggering the relay. Valid are 'low' 'high'
            or 'both'.

    :ivar status: The relay status.

    """
    def __init__(self, transport, protocol, idx):
        super(Relay, self).__init__(transport, protocol)
        idx = int(idx)
        self.config = Command(
            'RELAY? {0}'.format(idx),
            'RELAY {0},'.format(idx),
            [
                Enum('off', 'on', 'alarm', 'zone'),
                Enum('scan', *range(1, 17)),
                Enum('low', 'high', 'both')
            ]
        )
        self.status = Command(('RELAYST? {0}'.format(idx), Boolean))


class LS370(IEC60488):
    """A lakeshore mode ls370 resistance bridge.

    Represents a Lakeshore model ls370 ac resistance bridge.

    :param transport: A transport object.

    :ivar baud: The baud rate of the rs232 interface. Valid entries are `300`,
        `1200` and `9600`.
    :ivar beeper: A boolean value representing the beeper mode. `True` means
        enabled, `False` means disabled.
    :ivar brightness: The brightness of the frontpanel display in percent.
        Valid entries are `25`, `50`, `75` and `100`.
    :ivar common_mode_reduction: The state of the common mode reduction.
    :ivar control_mode: The temperature control mode, valid entries are
        'closed', 'zone', 'open' and 'off'.
    :ivar control_params: The temperature control parameters. *(<channel>,*
        *<filter>, <units>, <delay>, <output>, <limit>, <resistance>)*, where

        * *<channel>* The input channel used for temperature control.
        * *<filter>* The filter mode, either 'filtered' or 'unfiltered'.
        * *<units>* The setpoint units, either 'kelvin' or 'ohm'.
        * *<delay>* The delay in seconds used for the setpoint change during
          autoscan. An integer between 1 and 255.
        * *<output>* The heater output display, either 'current' or 'power'.
        * *<limit>* The maximum heater range. See :attr:`.Heater.RANGE`.
        * *<resistance>* The heater load in ohms. Valid entries are 1. to
          100000.

    :ivar digital_output: A register enabling/disabling the digital output
        lines.
    :ivar displays: A tuple of :class:`.Display` instances, representing the 7
        available display locations.
    :ivar display_locations: The number of displayed locations, between 1 and
        8.
    :ivar frequency: The excitation frequency. Valid entries are '9.8 Hz',
        '13.7 Hz' and '16.2 Hz'.

        .. note:: This commands takes several seconds to complete

    :ivar heater: An instance of the :class:`.Heater` class.
    :ivar ieee: The IEEE-488 interface parameters, represented by the following
        tuple *(<terminator>, <EOI enable>, <address>)*, where

        * *<terminator>* is `None`, `\\\\r\\\\n`, `\\\\n\\\\r` or `\\\\n`.
        * *<EOI enable>* A boolean.
        * *<address>* The IEEE-488.1 address of the device, an integer between
          0 and 30.

    :ivar input: An instance of :class:`~.Input`.
    :ivar input_change: Defines if range and excitation keys affects all or
        only one channel. Valid entries are 'all', 'one'.
    :ivar mode: Represents the interface mode. Valid entries are
        `"local"`, `"remote"`, `"lockout"`.
    :ivar monitor: The monitor output selection, one of 'off', 'cs neg',
        'cs pos', 'vad', 'vcm neg', 'vcm pos', 'vdif' or 'vmix'.
    :ivar output: A tuple, holding two :class:`.Output` objects
    :ivar pid: The pid loop settings. *(<p>, <i>, <d>)*, where

        * *<p>* The proportional gain, a float in the range 0.001 to 1000.
        * *<i>* The integral action, a float in the range 0 to 10000.
        * *<d>* The derivative action, a float in the range 0 to 2500.

    :ivar polarity: The polarity of the temperature control. Valid entries are
        'unipolar' and 'bipolar'.
    :ivar ramp: The setpoint ramping parameters. *(<enabled>, <rate>)*, where

        * *<enabled>* Is a boolean, enabling/disabling the ramping.
        * *<rate>* A float representing the ramping rate in kelvin per minute
          in the range 0.001 to 10.
    :ivar ramping: The ramping status, either `True` or `False`.
    :ivar low_relay: The low relay, an instance of :class:`~.Relay`.
    :ivar high_relay: The high relay, an instance of :class:`~.Relay`.
    :ivar setpoint: The temperature control setpoint.
    :ivar still: The still output value.

        .. note::

            The still only works, if it's properly configured in the analog
            output 2.

    :ivar all_curves: A :class:`.Curve` instance that can be used to configure
        all user curves simultaneously. Instead of iterating of the
        :attr:`.user_curve` attribute one can use this command. This way less
        commands will be send.
    :ivar user_curve: A tuple of 20 :class:`.Curve` instances.
    :ivar zones: A sequence of 10 Zones. Each zone is represented by a tuple
        *(<top>, <p>, <i>, <d>, <manual>, <heater>, <low>, <high>, <analog1>*
        *, <analog2>)*, where

        * *<top>* The setpoint limit of this zone.
        * *<p>* The proportional action, 0.001 to 1000.
        * *<i>* The integral action, 0 to 10000.
        * *<d>* The derivative action, 0 to 10000.
        * *<manual>* The manual output in percent, 0 to 100.
        * *<heater>* The heater range.
        * *<low>* The low relay state, either `True` or `False`.
        * *<high>* The high relay state, either `True` or `False`.
        * *<analog1>* The output value of the first analog output in percent.
          From -100 to 100.
        * *<analog2>* The output value of the second analog output in percent.
          From -100 to 100.

    """
    def __init__(self, transport, scanner=None):
        super(LS370, self).__init__(transport)
        self.baud = Command('BAUD?', 'BAUD', Enum(300, 1200, 9600))
        self.beeper = Command('BEEP?', 'BEEP', Boolean)
        self.brightness = Command('BRIGT?', 'BRIGT', Enum(25, 50, 75, 100))
        self.common_mode_reduction = Command('CMR?', 'CMR', Boolean)
        self.control_mode = Command(
            'CMODE?',
            'CMODE',
            Enum('closed', 'zone', 'open', 'off', start=1)
        )
        self.control_params = Command(
            'CSET?',
            'CSET',
            [Integer(min=0, max=16), Enum('unfiltered', 'filtered'),
             Enum('kelvin', 'ohm', start=1), Integer(min=0, max=255),
             Enum('current', 'power', start=1), Enum(*Heater.RANGE),
             Float(min=1., max=100000.)]
        )
        # TODO disable if 3716 scanner option is used.
        self.digital_output = Command(
            'DOUT?',
            'DOUT',
            Register({
                0: 'DO1',
                1: 'DO2',
                2: 'DO3',
                3: 'DO4',
                4: 'DO5'
            }),
        )
        self.displays = tuple(
            Display(transport, self._protocol, i) for i in range(1, 9)
        )
        self.display_locations = Command(
            'DISPLAY?',
            'DISPLAY',
            Integer(min=1, max=8)
        )
        self.frequency = Command(
            'FREQ?',
            'FREQ',
            Enum('9.8 Hz', '13.7 Hz', '16.2 Hz', start=1)
        )
        self.guard = Command('GUARD?', 'GUARD', Boolean)
        self.ieee = Command('IEEE?', 'IEEE',
                            [Enum('\r\n', '\n\r', '\n', None),
                             Boolean,
                             Integer(min=0, max=30)])
        # TODO only active if model scanner 3716 is installed.
        self.input_change = Command('CHGALL?', 'CHGALL', Enum('one', 'all'))
        self.mode = Command('MODE?', 'MODE',
                            Enum('local', 'remote', 'lockout', start=1))
        self.monitor = Command(
            'MONITOR?',
            'MONITOR',
            Enum('off', 'cs neg', 'cs pos', 'vad',
                 'vcm neg', 'vcm pos', 'vdif', 'vmix')
        )
        self.output = (
            Output(transport, self._protocol, 1),
            Output(transport, self._protocol, 2)
        )
        self.pid = Command(
            'PID?',
            'PID',
            [Float(min=1e-3, max=1e3), Float(min=0., max=1e4),
             Float(min=0, max=2.5e3)]
        )
        self.polarity = Command('CPOL?', 'CPOL', Enum('unipolar', 'bipolar'))
        self.ramp = Command(
            'RAMP?',
            'RAMP',
            [Boolean, Float(min=1e-3, max=10.)]
        )
        self.ramping = Command(('RAMPST?', Boolean))
        self.low_relay = Relay(transport, self._protocol, 1)
        self.high_relay = Relay(transport, self._protocol, 2)
        self.scanner = scanner
        self.setpoint = Command('SETP?', 'SETP', Float)
        self.still = Command('STILL?', 'STILL', Float)
        self.all_curves = Curve(transport, self._protocol, 0, 200)
        self.user_curve = tuple(
            Curve(transport, self._protocol, i, 200) for i in range(1, 21)
        )

        def make_zone(i):
            """Helper function to create a zone command."""
            type_ = [
                Float, Float(min=0.001, max=1000.), Integer(min=0, max=10000),
                Integer(min=0, max=10000), Integer(min=0, max=100),
                Enum(*Heater.RANGE), Boolean, Boolean,
                Integer(min=-100, max=100),Integer(min=-100, max=100)
            ]
            return Command('ZONE? {0}'.format(i), 'ZONE {0},'.format(i), type_)
        self.zones = CommandSequence(
            self._transport,
            self._protocol,
            (make_zone(i) for i in range(1, 11))
        )

    def clear_alarm(self):
        """Clears the alarm status for all inputs."""
        self._write('ALMRST')

    def _factory_default(self, confirm=False):
        """Resets the device to factory defaults.

        :param confirm: This function should not normally be used, to prevent
            accidental resets, a confirm value of `True` must be used.

        """
        if confirm is True:
            self._write(('DFLT', Integer), 99)
        else:
            raise ValueError('Reset to factory defaults was not confirmed.')

    def reset_minmax(self):
        """Resets Min/Max functions for all inputs."""
        self._write('MNMXRST')

    @property
    def scanner(self):
        """The scanner option in use.

        Changing the scanner option changes number of input channels available.
        Valid values are

        =======  ========
        scanner  channels
        =======  ========
        None     1
        '3708'   8
        '3716'   16
        '3716L'  16
        =======  ========

        """
        return self._scanner

    @scanner.setter
    def scanner(self, value):
        channels = {
            None: 1,
            '3716': 16,
            '3716L': 16,
            '3708': 8,
        }
        self.input = Input(self._transport, self._protocol, channels=channels[value])
        self._scanner = value
