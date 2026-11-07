# Documented Injected Bugs

This file details the single injected bug in each buggy variant located under `designs/rtl_bug/`.

| Design | File | Bug Description | Expected Behavior | Buggy Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **counter** | `designs/rtl_bug/counter.v` | Wrap on saturation | When `count == 15` and `en == 1`, count should saturate and remain 15. | `count` rolls over from 15 to 0 on the next enabled clock edge (`count <= count + 1`). |
| **fifo** | `designs/rtl_bug/fifo.v` | Overflows on write when full | Writes should be ignored when `full == 1`. | FIFO accepts writes even when `full == 1` (`wr_valid = wr_en`), overwriting contents and advancing count past capacity. |
| **arbiter** | `designs/rtl_bug/arbiter.v` | Priority removed | Mutual exclusion with strict priority for `req0` over `req1`. If both request, only `gnt0` is granted. | Priority arbitration is removed (`gnt0 <= req0; gnt1 <= req1;`), granting both simultaneously when both request. |
| **traffic** | `designs/rtl_bug/traffic.v` | Premature transition / state skip | FSM must cycle `RED -> GREEN -> YELLOW -> RED`. | GREEN skips the YELLOW state and transitions directly back to RED (`GREEN: state <= RED`). |
| **shift_reg** | `designs/rtl_bug/shift_reg.v` | Inverted control priority | `load` must have priority over `shift_en`. | `shift_en` is given priority over `load`, so asserting both shifts instead of loading `din`. |
| **pwm** | `designs/rtl_bug/pwm.v` | Off-by-one threshold comparison | Output must be high strictly when `cnt < duty`. When `duty == 0`, output must always be low. | Comparison uses `<=` instead of `<` (`cnt <= duty`), causing output to be high when `cnt == duty` (and active even when `duty == 0`). |
