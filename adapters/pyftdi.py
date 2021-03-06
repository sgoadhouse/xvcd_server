#------------------------------------------------------------------------------
# Copyright 2014 Kyle J. Temkin <ktemkin@binghamton.edu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
# The above copyright is for the ftdi.py code that this is based on. Changes
# are Copyright 2018 S. Goadhouse <sgoadhouse@virginia.edu>
#
#------------------------------------------------------------------------------

from bitstring import BitStream, BitArray, Bits
from adapters.jtag import jtag

# INSTALLATION NOTE:
#
# To work on macOS, after install libusb and pyftdi, may have to
# unload any existing FTDI drivers so they do not grab the device
# before this code can. To do this:
#
#   sudo kextunload -bundle-id com.FTDI.driver.FTDIUSBSerialDriver
#   sudo kextunload -bundle-id com.apple.driver.AppleUSBFTDI
#
# Can use kextload or rebotting to allow the drivers to work again -
# this may impact any other FTDI devices that you want to run in VCOM
# mode.

class PyFTDIAdapter(jtag):
    """ 
        A JTAG adapter for FTDI-based devices based on the python PyFTDI library and using MPSSE mode.
    """

    def __init__(self, device):
        """
            Create a new FTDI JTAG connection.

            device -- The PyFTDI device to connect to.
        """
        
        #Initiatialize the core JTAG subsystem.
        super().__init__()

        #... and store the newly created device.
        self.device = device

        #Create a copy of the instruction register for this device.
        #self.ir = Bits('0b000000')

    def set_verbosity(self, level):
        """
            Sets the verbosity level, as per the command line.
        """
        self.verbosity_level = level


    def set_frequency(self, frequncey):
        """
            Set the TCK Frequency
        """
        ## @@@ NOTE: The initial frequency that is passed in during
        ## configuration/open does not seem to work and a call here is
        ## needed after things are opened to properly set the
        ## frequency.
        actualFreq = self.device.set_frequency(frequency)

        if (self.verbosity_level >= 1):
            print("Requested Freq: {}  Actual Freq: {}".format(1e9/period, actualFreq))
            
        return actualFreq

    def set_tck_period(self, period):
        """
            Handle the settck virtual cable command which requests a certain TCK period. Return the actual period.
        """

        return int(1e9/self.set_frequency(1e9/period))

    @property
    def max_byte_sizes(self):
        """Return the 3-tuple of maximum bytes from (TMS, TDI (output) and TDO (input))

           :return: 3-tuple of write, read buffer sizes in bytes
           :rtype: tuple(int, int)
        """
        return self.device.max_byte_sizes

    @property
    def xvc_vector_len(self):
        """Return the recommended vector length. This appears to be a byte length that includes both the TMS and TDI vectors

           :return: integer that the the maximum xvc_vector_len to report back to Vivado
           :rtype: int
        """
        return 8100

    def send_data(self, tms_stream, tdi_stream):
        """
            Performs a general-purpose JTAG communication.

            tms_stream -- The values to be transmitted over the Test Mode Select (TMS) line.
            tdi_stream -- The values to be transmitted to the target device.
        """

        ## Check data sizes first
        #@@@ if (tms_stream.len > self.max_byte_sizes[0]):
        #@@@    raise ValueError('TMS bit stream size ({}) is too big for JTAG adapter (max: {})'.format(tms_stream.len,self.max_byte_sizes[0]))

        ## Check TDI size against both TDI and TDO buffer sizes since the TDO stream size will equal the TDI input stream size.
        #@@@if (tdi_stream.len > min(self.max_byte_sizes[1:3])):
        #@@@    raise ValueError('TDI bit stream size ({}) is too big for JTAG adapter (max: {})'.format(tms_stream.len,min(self.max_byte_sizes[1:3])))
 
            
        #Create a new bitstream object to store the result of the transmission.
        tdo_stream = BitArray()

        # Although the PyFTDI MPSSE mode is expected to be a
        # significant performance improvement over GPIO mode, it does
        # have an unfortunate complexity with how the TMS signal is
        # handled.
        #
        # The shift: VCD command sends a TMS bit vector and a TDI bit
        # vector of the same size so that each bit of TMS corresponds
        # to each bit of TDI. However, TMS is only needed which
        # changing the JTAG TAP state machine. So the FTDI MPSSE
        # registers only accept up to 7 consecutive settings of TMS
        # with a single TDI bit output for each TMS output. Since more
        # than 5 consecutive TMS high means reset, this is not a
        # limitation against JTAG but makes interfacing with XVCD a
        # little more challenging.
        #
        # So this will have to be handled by searching for when TMS is
        # a '1', breaking up the bitstring and sending in pieces to
        # the JtagController so that TMS gets handled properly.
        #
        # Also, all of the Jtag functions are written with bits
        # handled through the BitSequence object which appears to make
        # the right-most bit in an array the lsb. This is opposite to
        # the open source bitstring, which is used here and in lots of
        # places. It has the lsb at the left-most bit in the array. So
        # instead of bit swapping again for BitSequence, simply
        # rewrite the worker functions from JtagController to use
        # bitstring and to use different command opcodes to handle
        # bitstrings properly.
        

        # First, search through TMS bit vector for the next '1'.
        #
        # Send out all of the TDI bits before TMS is '1'
        #
        # Grab the next section of bits where TMS is high plus it
        # being low once and grab TDI when it is first low for it to
        # be the TDI setting during the next sequence.
        #
        # Repeat until done

        head = 0                # head of bit sequence of interest
        while (head < len(tms_stream)):
            # Find position of the next bit where TMS is '1'
            tms1Find = tms_stream.find('0b1', start=head)

            if tms1Find:
                # If a '1' exists, save its bit position
                tms1Pos = tms1Find[0]
            else:
                # Else, set its position to the end
                tms1Pos = len(tms_stream)

            # Handle the bit sequence where TMS is a '0' - focus on
            # sending TDI out with TMS set to '0'.
            #
            # First, check that tms1Pos has advanced past head,
            # otherwise, it is another segment where TMS is '1', so
            # skip to below.
            if (tms1Pos > head):
                ## Handle TDI bits with TMS = '0'
                #
                if (self.verbosity_level >= 4):
                    print('Bit Segment with TMS as "0": ', tms_stream[head:tms1Pos], 'Head: {} TMS1Pos:{} TMS Pos: {}'.format(head, tms1Pos, tms_stream.pos))

                # Write out the TDI bits with TMS set to '0'
                tdo_stream += self.device.write_tdi_read_tdo(tdi_stream[head:tms1Pos])

            # Advance head to next bit segment. If completed all bits, break out of loop
            head = tms1Pos
            if head >= len(tms_stream):
                break

            # Find position of the next bit where TMS is '0'
            tms0Find = tms_stream.find('0b0', start=head)

            if tms0Find:
                # If a '0' exists, save its bit position. Since we
                # want the last TMS bit sent in this section to return
                # to '0', increase the position by 1.
                tms0Pos = tms0Find[0]+1
            else:
                # Else, found no '0' so set its position to the end
                tms0Pos = len(tms_stream)
                
            # Handle the bit sequence where TMS is a '1' with a single
            # '0' unless have reached the end of the bit sequence.
            #
            # Will send out TMS with TDI set to the value when TMS is
            # '0'. If TMS as '0' was not found, set TDI to the last
            # value given.
            #
            # First, check that tms0Pos has advanced past head,
            # otherwise, it is another segment where TMS is '0', so
            # skip to above.
            while (tms0Pos > head):

                # Can only write a maximum of 7 TMS bits so make this
                # next segment a maximum of 7 bits and repeat until
                # this TMS as "1" segment is sent.
                tail = min(tms0Pos,head+7)

                #@@@if (self.verbosity_level >= 1):
                #    if (tdi_stream[head:tail] != Bits(int=0, length=(tail-head)) and
                #        tdi_stream[head:tail] != Bits(int=-1, length=(tail-head))):
                #        print('^^^ TDI Segment with TMS as "1" is not constant! TDI: ', tdi_stream[head:tail], ' TMS: ', tms_stream[head:tail])

                # If TDI is not constant during this TMS is '1'
                # segment, then break it up further so can send a
                # static TDI.
                #
                # Find position of the next bit where TDI changes
                tdiFind = tdi_stream.find(Bits(bool=not tdi_stream[head]), start=head, end=tail)
                if tdiFind:
                    # If TDI changed during this segment, then break
                    # up the segment so that TDI does not change with
                    # each write_tms_tdi_read_tdo() call
                    tail = tdiFind[0]

                if (self.verbosity_level >= 4):
                    print('Bit Segment with TMS as "1": ', tms_stream[head:tail], 'Head: {} Tail: {} TMS0Pos:{} TMS Pos: {}'.format(head, tail, tms0Pos, tms_stream.pos))

                # Check the assumption that TDI does not change during
                # this bit sequence where TMS is a '1'. It should not
                # since it is now checked above with find of
                # tdi_stream
                if (self.verbosity_level >= 3):
                    if (tdi_stream[head:tail] != Bits(int=0, length=(tail-head)) and
                        tdi_stream[head:tail] != Bits(int=-1, length=(tail-head))):
                        print('TDI Segment with TMS as "1" is not constant! TDI: ', tdi_stream[head:tail], ' TMS: ', tms_stream[head:tail])
                
                # Write out the TMS bits with TDI set to the final bit
                # in the sequence.
                tdo_stream += self.device.write_tms_tdi_read_tdo(tms_stream[head:tail], tdi_stream[tail-1])

                # Advance head to next bit segment.
                head = tail

            # If have sent all bits, head will equal len(tms_stream) and
            # therefore will complete loop

        #... return the values returned over TDO.
        return tdo_stream

    
    def set_program(self, value):
        """
            Set the value of the program pin. This will need to be designed on
            a frontend basis, where supported.
        """
        pass

    def reset(self):
        """
            Reset the target device, where supported.
        """
        pass




