# NepTweaks - PSVita

A collection of patches for Hyperdimension Neptunia U: Action Unleashed (PSVita North American release) that makes the game better (for me!!). These patches do kill off the original "Cheats" menu in the config.

## Patches

- No more costume break (yay no more pause & yay no clothes change)

- 60fps

- Retire in any quest

## How to apply the patch

1. Run ```pip install -r requirements.txt```

2. Use FAGDec to get the unencrypted SELF (`raw/eboot.bin`) and ELF (`raw/eboot.bin.elf`)

3. Copy `m/ui/config_2d.cat` from the decrypted game (VitaShell -> Open decrypted) to `raw/m/ui/`

4. Patch the ELF:
   `python3 patch.py raw/eboot.bin.elf eboot_patched.elf`

5. Inject it into the FAGDec SELF:
   `python3 patcher.py raw/eboot.bin raw/eboot.bin.elf eboot_patched.elf patch/eboot.bin`

6. Build the menu labels:
   `python3 build_assets.py raw/m/ui/config_2d.cat patch/m/ui/config_2d.cat`

7. Build the option descriptions:
   `python3 build_text.py raw/m/text/text.cat patch/m/text/text.cat`
   
8. Copy the contents of `patch/` to `ux0:rePatch/PCSE00588/` (needs rePatch 2.71+):

   ```
   ux0:rePatch/PCSE00588/eboot.bin
   ux0:rePatch/PCSE00588/m/ui/config_2d.cat
   ux0:rePatch/PCSE00588/m/text/text.cat
   ```
