# Govee H7140 – BLE Protocol Notes

Diese Referenz wurde aus **Live-Verkehr mit einem H7140** (App 7.7.02, Firmware 1.00.29, Hardware 1.02.00) und aus dem öffentlich dokumentierten Govee-Appliance-Protokoll abgeleitet. Sie ist keine offizielle Govee-Spezifikation.

## GATT

| Rolle | UUID |
|---|---|
| Service | `00010203-0405-0607-0809-0a0b0c0d1910` |
| Write (Write Without Response) | `00010203-0405-0607-0809-0a0b0c0d2b11` |
| Notify | `00010203-0405-0607-0809-0a0b0c0d2b10` |

Es existiert zusätzlich der Govee-Sensor-Service `494e5445-4c4c-495f-524f-434b535f4857` (`INTELLI_ROCKS_HW`); für die Steuerung wird er hier nicht benötigt.

Nur **ein BLE-Central** kann gleichzeitig verbinden. Die Govee-App auf dem Handy muss geschlossen sein.

## Frame-Format

Alle Anwendungsframes sind 20 Byte:

```text
Byte 0      Präfix: 0x33 Write, 0x3A Write/Read, 0xAA Query-Response,
                    0xEE Notification
Byte 1      Kommando
Byte 2..18  Payload, mit Nullen aufgefüllt
Byte 19     XOR-Prüfsumme der Bytes 0..18
```

Beispiel Power On:

```text
33 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 33
```

## Verschlüsselung (Govee V1)

Der H7140 kann Klartext **oder** eine verschlüsselte Session verwenden. Die Integration probiert zunächst Klartext und führt bei Bedarf den V1-Handshake aus.

- Kommunikationsschlüssel: `MakingLifeSmarte` (16 Byte)
- Verschlüsselung pro 20-Byte-Frame:
  - Bytes 0–15: AES-128-ECB
  - Bytes 16–19: XOR mit einem RC4-kompatiblen Keystream, initialisiert mit demselben Schlüssel
- Handshake:
  1. `e7 01` + 17 Zufallsbytes, XOR-Prüfsumme, mit dem Kommunikationsschlüssel verschlüsseln, schreiben.
  2. Antwort entschlüsseln: `e7 01` + **Session-Key** in Bytes 2–17.
  3. `e7 02` + 17 Zufallsbytes, mit dem Kommunikationsschlüssel verschlüsseln, schreiben; Gerät echo't den Frame.
  4. Alle weiteren Frames mit dem **Session-Key** ver- und entschlüsseln.
- Der Session-Key gilt nur für diese BLE-Verbindung.
- Advertisement-Daten bleiben unverschlüsselt.

Beispiel: verschlüsselter Wire-Frame → Klartext

```text
Wire : c9 4e 0a 20 96 04 df df f3 07 ef 3c a0 20 ea 8b 68 ee 40 60
Plain: aa 01 00 00 01 03 6c fa 00 00 00 00 00 00 00 00 00 00 00 3f
```

(Entschlüsselt mit `MakingLifeSmarte`.)

## Abfragen

Die folgenden Frames werden an `…2b11` geschrieben; die Antworten kommen auf `…2b10`.

| Zweck | Query | Antwort |
|---|---|---|
| Status / Wasser | `AA 01` | `AA 01 …` |
| Kompaktstatus | `AA 10` | `AA 10 …` |
| Betriebsmodus | `AA 05 00` | `AA 05 00 <mode>` |
| Manuelle Stufe | `AA 05 01` | `AA 05 01 <1..8>` |
| Custom-Parameter | `AA 05 02` | `AA 05 02 <16 Byte>` |
| Ziel-Luftfeuchte | `AA 05 03` | `AA 05 03 <40..80>` |
| Timer-Rohdaten | `AA 16` | `AA 16 <payload>` |
| Flags | `AA 17` | `AA 17 <flag0> <flag1>` |
| Stufengrenzen | `AA 1C` | `AA 1C <low> <high>` |
| Nachtabtlicht | `AA 1B 01` | `AA 1B 01 <on> <brightness>` |
| Nachtabtlicht RGB | `AA 1B 05` | `AA 1B 05 0D <R><G><B>` |
| Nachtabtlicht-Szene | `AA 1B 04` | `AA 1B 04 …` (noch nicht dekodiert) |
| Firmware | `AA 06` | ASCII |
| Hardware | `AA 20` | ASCII |
| Software | `AA 21` | ASCII |
| Seriennummer | `AA 07 02` | 8 Byte |
| Hardware-Version | `AA 07 03` | ASCII |
| MAC | `AA 07 06` | 6 Byte |
| MCU-SW | `AA 07 0A` | ASCII |
| MCU-HW | `AA 07 0B` | ASCII |
| BLE-MAC | `AA 14` | 6 Byte (umgekehrt) |
| Pact | `AA EF` | `00 <type> <code>` |

### Status `AA 01`

Live-Beispiele (entschlüsselt):

```text
Tank leer:  aa 01 00 00 01 03 6c f3 00 00 01 00 00 00 00 00 00 00 00 …
Tank voll:  aa 01 00 00 01 03 6c f3 00 00 00 00 00 00 00 00 00 00 00 …
```

- **Byte 10** (Frame-Offset, also `payload[8]`) = `0x01` bei **Wassertank leer / Lack Water**. Das ist der verifizierte Wasser-Flag.
- Die übrigen Bytes sind firmwareabhängig und nicht als stabiler Power-/Modus-Wert dokumentiert. Die Integration nutzt für Ein/Aus und „befeuchtet gerade“ das Advertisement-Byte 4.
- `AA 10` liefert eine kompakte Teilmenge: `AA 10 <…> <…> <…>`.

### Modus

```text
aa 05 00 01 …   Manual
aa 05 00 02 …   Custom
aa 05 00 03 …   Auto
```

`AA 05 01` liefert die manuelle Stufe (verifiziert: `08`, nach Write `05`).
`AA 05 03` liefert die Ziel-Luftfeuchte (verifiziert: `0x37` = 55, `0x38` = 56).
`AA 1C` liefert die vom Gerät gemeldeten Grenzen (verifiziert: `01 08`).

### Custom-Parameter `AA 05 02`

Beispiel (verifiziert):

```text
aa 05 02 00 08 00 3c 00 00 05 00 3c 00 00 01 ff ff ff ff
```

Feldbedeutung (live durch Write/Query verifiziert):

| Byte | Bedeutung |
|---|---|
| 0 | immer `0` (vom Gerät zurückgesetzt) |
| 1 | hohe Stufe (1–8) |
| 3 | Dauer hohe Stufe in Minuten |
| 5 | Spiegel von Byte 3 (Gerät normalisiert) |
| 6 | niedrige Stufe (1–8) |
| 8 | Dauer niedrige Stufe in Minuten |
| 10 | Spiegel von Byte 8 |
| 11 | `1` (vom Gerät beibehalten; Write wird ignoriert) |
| 12–15 | `ff ff ff ff` (keine weitere Zeit) |

Ein Write `3A 05 02 …` setzt die Parameter **und schaltet in den Custom-Modus**
(`AA 05 00` wird `02`). Das Gerät sendet zusätzlich `EE 05 02 …` als Push.
Die Integration bildet daraus vier Number-Entities.

### Flags `AA 17`

Live (verschlüsselte Session): `aa 17 00 00 …`. Die Bedeutung von Byte 2/3 ist nicht gesichert (Auto-Stop / Child-Lock-Kandidaten). Ein Write `3a 17 01 01` wurde vom Gerät zwar echo't, änderte den Status aber nicht. Deshalb ist der Auto-Stop-Schalter **experimentell und standardmäßig deaktiviert**.

### Nachtabtlicht

Verifizierte Zustände/Writes:

```text
Query:          aa 1b 01
Antwort:        aa 1b 01 <on> <brightness>
Power On:       3a 1b 01 01 01
Power Off:      3a 1b 01 01 00
Helligkeit 50:  3a 1b 01 02 32
RGB Grün:       3a 1b 05 0d 00 ff 00
RGB Query:      aa 1b 05  →  aa 1b 05 0d <R><G><B>
```

Die Helligkeit bleibt beim Ausschalten erhalten. Die fünf Cloud-Szenen (Forest/Ocean/Wetland/Leisurely/Sleep) konnten mit `3a 1b 04 <1..5>` **nicht** gesetzt werden (Gerät normalisierte auf `3a 1b 04 00`); die Szenen bleiben experimentell/deaktiviert.

## Steuerbefehle

| Aktion | Frame |
|---|---|
| Ein | `33 01 01` (bei leerem Tank / Schutzmodus ggf. physische Power-Taste) |
| Aus | `33 01 00` (live bestätigt) |
| Manuell, Stufe 5 | `3a 05 01 05` |
| Auto, Ziel 55 % | `3a 05 03 37` |
| Custom (16-Byte-Payload) | `3a 05 02 <16 Byte>` |
| Nachtabtlicht an | `3a 1b 01 01 01` |
| Nachtabtlicht aus | `3a 1b 01 01 00` |
| Helligkeit 50 % | `3a 1b 01 02 32` |
| RGB | `3a 1b 05 0d <R><G><B>` |

Verifizierte Antworten auf Writes:

```text
3a 05 03 38 → 3a 05 03 38 (Echo), ee aa 01 …, aa 01 …, aa 05 03 38
3a 05 01 05 → 3a 05 01 05 (Echo), aa 05 00 01, aa 05 01 05
3a 1b 01 01 01 → 3a 1b 01 01 32 (Power on, Helligkeit 50 bleibt)
3a 1b 05 0d 00 ff 00 → 3a 1b 05 0d 00 ff 00, aa 1b 05 0d 00 ff 00
33 01 00 → 33 01 00, ee aa 01 00, aa 01 …, Advertisement Byte 4: 1 → 0
```

## Advertisement

Beobachtete Herstellerdaten (ohne Company-ID, Company-ID `0x8802` bzw. `0x8843`):

```text
0x8802: ec 00 01 02 01 40   # aktiv/befeuchtend, Byte 5 = 64
0x8802: ec 00 01 02 00 40   # an, aber idle
0x8843: ec 00 02 01 01 00   # aktiv, Byte 5 = 0
0x8843: ec 00 02 01 00 00   # aus/idle
0x8843: ec 00 02 01 00 40   # anderes Gerät, Byte 5 = 64
```

- **Byte 4** = befeuchtet gerade / aktiv (`1`) oder nicht (`0`). `1` bestätigt „an“; `0` kann auch „Ziel erreicht / idle“ bedeuten. Die Integration setzt „aus“ deshalb nur durch ein explizites `33 01 00` (oder den initialen Zustand), nicht durch jedes idle-Advertisement.
- **Byte 5** = aktuelle Luftfeuchte in Prozent, sofern `1..100`; sonst unbekannt. Die Govee-Cloud-API liefert diesen Wert nicht.
- **Byte 2/3** sind pakettypabhängig (`01 02` bzw. `02 01`); nicht als Power-Flag verwenden.
- Das Gerät sendet je nach Zustand/Verbindung `0x8802` oder `0x8843`. Beide IDs werden erkannt.

## Geräteinformationen (Live)

```text
Firmware:       1.00.29
Hardware:       1.02.00
MCU-SW:         1.00.10
MCU-HW:         1.01.02
Seriennummer:   90 44 20 07 C9 D0 C9 15
BLE-MAC:        90:44:20:07:C9:D0
Pact:           2/1 (verschlüsselte Session)
```

## Nicht verifiziert / offen

- Timer-/Zeitplanformat (`AA 16`, `AA 17`): Rohdaten werden angezeigt, aber nicht geschrieben.
- Nachtlicht-Szenen: Kommando noch nicht gefunden; der `send_frame`-Service kann zum Testen genutzt werden.
- Auto-Stop/Child-Lock: Kandidaten in `AA 17`, Write noch nicht bestätigt.
- Bedeutung der Telemetrie-Bytes 6/7 in `AA 01` (ändern sich langsam; vermutlich Zähler/Timer, nicht Luftfeuchte).
- Verschlüsselte Session bei anderen Firmware-Ständen: Die Integration erkennt Klartext vs. V1 automatisch; ein V2-Handshake ist nicht implementiert.

## Quellen

- Live-BLE-Captures mit einem H7140 (Firmware 1.00.29), inkl. verschlüsselter Session.
- Öffentliche Govee-BLE-Protokollnotizen für H7124/H7129 (gleiche 20-Byte-Framing- und V1-Krypto-Familie).
- Govee-Cloud-Capabilities des H7140 (Power, workMode, humidity, nightlightToggle, brightness, colorRgb, nightlightScene, lackWaterEvent).
