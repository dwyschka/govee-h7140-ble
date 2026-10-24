# Govee H7140 BLE – Home Assistant Custom Integration

Lokale Bluetooth-Steuerung für den **Govee / GoveeLife H7140 Smart Humidifier Lite** – ohne WLAN, ohne Govee-Cloud und ohne LAN-API.

Die Integration spricht das 20-Byte-Govee-BLE-Protokoll direkt. Der H7140 verwendet ab bestimmten Firmware-Ständen eine **Govee-V1-verschlüsselte Session** (AES-128-ECB + RC4-Tail, Handshake `e7 01`/`e7 02`); die Integration erkennt automatisch, ob das Gerät Klartext oder verschlüsselt antwortet, und führt den Handshake bei Bedarf aus.

## Funktionen

| Funktion | Status |
|---|---|
| Ein/Aus (Befeuchterbetrieb) | ✅ Aus live bestätigt; Ein via `33 01 01` (bei Schutzmodus ggf. physische Power-Taste) |
| Betriebsmodus Manuell / Benutzerdefiniert / Auto | ✅ verifiziert |
| Ziel-Luftfeuchte 40–80 % | ✅ verifiziert |
| Manuelle Nebelstufe 1–8 | ✅ verifiziert |
| Nachtabtlicht Ein/Aus | ✅ verifiziert |
| Nachtabtlicht-Helligkeit 1–100 % | ✅ verifiziert |
| Nachtabtlicht RGB | ✅ verifiziert |
| Aktuelle Luftfeuchte aus Advertisement | ✅ (Byte 5; optional) |
| Wassertank leer / Lack-Water | ✅ (Statusbyte; Binary Sensor) |
| Firmware / Hardware / MCU / Seriennummer / BLE-MAC | ✅ |
| Auto-Stop | ⚠️ experimentell, standardmäßig deaktiviert |
| Nachtabtlicht-Szenen (Forest/Ocean/Wetland/Leisurely/Sleep) | ⚠️ experimentell, standardmäßig deaktiviert |
| Timer / Zeitpläne | ❌ noch nicht modelliert (Roh-Frame-Service vorhanden) |

## Voraussetzungen

- Home Assistant 2025.1 oder neuer
- Bluetooth-Adapter oder ESPHome-Bluetooth-Proxy in Reichweite
- H7140 eingeschaltet und **nicht** mit der Govee-App auf dem Handy verbunden (nur ein BLE-Central gleichzeitig)
- Bei leeren Wassertank schaltet das Gerät in einen Schutzmodus. Nach dem Auffüllen ggf. die **Power-Taste am Gerät** drücken; ein reiner BLE-Power-Befehl wird in diesem Zustand ignoriert.

## Installation über HACS

1. HACS → Integrationen → Drei-Punkte-Menü → **Benutzerdefinierte Repositories**
2. Repository-URL dieses Projekts eintragen, Kategorie **Integration**
3. **Govee H7140 BLE** installieren
4. Home Assistant neu starten
5. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Govee H7140 BLE**
   - Das Gerät wird über das Advertisement automatisch gefunden (`ihoment_H7140_…`).
   - Alternativ die Bluetooth-Adresse / macOS-CoreBluetooth-UUID manuell eingeben.

### Manuelle Installation (ohne HACS)

Den Ordner `custom_components/govee_h7140_ble` nach
`<HA-Konfiguration>/custom_components/govee_h7140_ble` kopieren, Home Assistant
neu starten und die Integration über die UI hinzufügen.

## Konfiguration

### Optionen

- **Abfrageintervall**: Standard 20 s
- **Nach Leerlauf trennen**: Standard 25 s; `0` trennt sofort nach jeder Aktion
- **Aktuelle Luftfeuchte aus Advertisement**: Byte 5 des Hersteller-Payloads; die Govee-Cloud-API liefert diesen Wert nicht
- **Experimentelle Funktionen**: Freischaltung der beiden folgenden Optionen
- **Experimentelle Szenen**: ergänzt die fünf Nachtabtlicht-Szenen
- **Experimenteller Auto-Stop-Schalter**: ergänzt einen Schalter für den 0x17-Selektor

### Entitäten

- `humidifier`: Hauptgerät (Ein/Aus, Ziel-Luftfeuchte, Modus, Aktion)
- `light.night_light`: Nachtabtlicht (RGB, Helligkeit, ggf. Szenen)
- `sensor.current_humidity`: aktuelle Luftfeuchte aus dem Advertisement
- `sensor.target_humidity`, `sensor.work_mode`, `sensor.mist_level`
- `sensor.low_gear`, `sensor.high_gear` (vom Gerät gemeldete Stufengrenzen)
- `sensor.firmware`, `sensor.hardware`, `sensor.mcu_firmware`, `sensor.mcu_hardware`
- `sensor.serial`, `sensor.ble_mac`, `sensor.rssi`, `sensor.last_seen`
- `binary_sensor.water_tank_empty` (Problem)
- `number.mist_level`: manuelle Nebelstufe (schaltet in den manuellen Modus)
- `switch.auto_stop` (nur experimentell)
- `button.refresh`

### Roh-Frame-Service

Für Diagnose und noch nicht modellierte Features:

```yaml
service: govee_h7140_ble.send_frame
target:
  device_id: <device_id>
data:
  frame: "AA 05 03"      # oder ein kompletter 20-Byte-Frame
  expect_response: true
```

Der Service gibt die erste `AA`-Antwort als `response` zurück. Bei verschlüsselten Geräten wird der Frame automatisch mit der aktuellen Session verschlüsselt.

## Protokoll

Die vollständige, aus Live-Captures abgeleitete Kommandoreferenz steht in [docs/protocol.md](docs/protocol.md).

Kurzfassung:

- Service `00010203-0405-0607-0809-0a0b0c0d1910`
- Write `…2b11` (Write Without Response), Notify `…2b10`
- 20-Byte-Frames, letztes Byte = XOR der Bytes 0–18
- Klartext **oder** Govee V1 (AES-128-ECB + RC4, Handshake `e7 01`/`e7 02`, Kommunikationsschlüssel `MakingLifeSmarte`, danach Session-Key)
- Power: `33 01 01` / `33 01 00`
- Modus/Ziel: `3A 05 01 <Stufe>`, `3A 05 02 <16 Byte>`, `3A 05 03 <Feuchte>`
- Nachtabtlicht: `3A 1B 01 01 <an/aus>`, `3A 1B 01 02 <Helligkeit>`, `3A 1B 05 0D <R><G><B>`

## Bekannte Einschränkungen

- **Ein/Aus-Semantik**: Der H7140 bleibt im Standby per BLE erreichbar. Die Integration setzt `is_on`/`action` anhand des „humidifying“-Bits im Advertisement (Byte 4) und des letzten `33 01`-Befehls. Ein `33 01 00` stoppt die Befeuchtung; das Gerät kann dabei weiterhin Advertisement und GATT-Queries beantworten. Das ist kein elektrisches Ausschalten.
- **Power-Taste nach Schutzabschaltung**: Bei leerem Tank geht der H7140 in einen Schutz-/Standby-Zustand. Nach dem Auffüllen kann ein BLE-`33 01 01` ignoriert werden; dann hilft die physische Power-Taste. Das ist eine Geräte-Firmware-Eigenschaft, keine Integrationseinschränkung.
- **Ein BLE-Central**: Die Govee-App auf dem Handy muss geschlossen sein, sonst kann Home Assistant nicht verbinden.
- **macOS**: CoreBluetooth verwendet UUIDs, die sich nach Power-Cycles ändern können. Unter Linux/BlueZ ist die MAC stabil. Auf macOS ggf. die Integration neu hinzufügen.
- **Szenen / Auto-Stop**: Die Frames sind noch nicht vollständig verifiziert und deshalb standardmäßig deaktiviert. Der Roh-Frame-Service hilft beim Testen.
- **Timer**: Die App besitzt Zeitplanseiten; das BLE-Timerformat (`aa 16`/`aa 17`) ist noch nicht vollständig entschlüsselt.
- **Aktuelle Luftfeuchte**: Wird aus dem Advertisement gelesen. Wenn das Gerät `0` sendet (kein Sensor / Standby), bleibt der Sensor unbekannt.

## Fehlersuche: „überall unbekannt“

- **Falsches Gerät eingerichtet?** In Reichweite waren zwei H7140: `ihoment_H7140_4491` (antwortet, V1-verschlüsselt, getestet) und `ihoment_H7140_3D13` (Advertisement `ec 00 02 01 00 40`, Verbindung lief im Test in einen Timeout). Wenn HA den 3D13-Eintrag nutzt, bleiben alle GATT-Werte unbekannt und das Nachtlicht reagiert nicht.
- **Gerät aufwecken:** Power-Taste am Gerät drücken, Wassertank prüfen. Ein Standby-/Schutzgerät nimmt ggf. keine GATT-Verbindung an.
- **Govee-App schließen** und Bluetooth am Handy kurz ausschalten; nur ein BLE-Central gleichzeitig.
- **Logs:** Bei fehlgeschlagener Protokollaushandlung steht `BLE protocol negotiation failed` bzw. `could not connect` im Log. Diagnose über Einstellungen → Geräte & Dienste → Govee H7140 BLE → Diagnose.
- **Nachtlicht** wird über GATT geschrieben (`3A 1B …`) und funktioniert nur, wenn die Integration verbinden kann. Am getesteten 4491 wurde es auch im Standby verifiziert.

## Debugging

```yaml
logger:
  default: warning
  logs:
    custom_components.govee_h7140_ble: debug
```

Diagnose: Einstellungen → Geräte & Dienste → Govee H7140 BLE → Diagnose. Enthält den letzten Zustand, Advertisement, Session-/Verbindungsstatus und die letzten Roh-Frames (ohne Schlüssel).

## Lizenz

MIT – siehe [LICENSE](LICENSE). Keine Verbindung zu Govee; inoffizielles Projekt.
