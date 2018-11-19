from common.constants import gameModes
from pp import rippoppai
from pp import wifipiano3
from pp import cicciobello

PP_CALCULATORS = {
    gameModes.STD: rippoppai.oppai,
    gameModes.TAIKO: rippoppai.oppai,
    gameModes.CTB: cicciobello.Cicciobello,
    gameModes.MANIA: wifipiano3.WiFiPiano
}
