from common.constants import gameModes
from pp import ez
from pp import wifipiano3
from pp import cicciobello

PP_CALCULATORS = {
    gameModes.STD: ez.Ez,
    gameModes.TAIKO: ez.Ez,
    gameModes.CTB: cicciobello.Cicciobello,
    gameModes.MANIA: wifipiano3.WiFiPiano
}
