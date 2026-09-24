# Zusatz: Motoranschlüsse am SKR Pico

Die Kabelfarben in der Grafik sind nur ein Beispiel. Bei Schrittmotoren können
Kabelfarben und Steckerbelegung je nach Lieferung abweichen. Entscheidend sind
nicht die Farben, sondern die zwei Spulenpaare des Motors.

Vor dem Umstecken die Hauptversorgung und USB trennen. Schrittmotoren nie bei
eingeschaltetem Board abziehen oder aufstecken, da dabei der TMC2209-Treiber
beschädigt werden kann.

## Grundprinzip

Ein 4-adriger bipolarer Schrittmotor hat zwei getrennte Spulen. Jeweils zwei
Kabel gehören zusammen und müssen gemeinsam an eine Treiberphase:

- Spule 1 an `1A` und `1B`
- Spule 2 an `2A` und `2B`

Die beiden Spulen dürfen nicht gemischt werden. Wenn ein Kabel von Spule 1 und
ein Kabel von Spule 2 auf derselben Treiberphase liegen, brummt oder vibriert
der Motor meist nur und hat kaum Drehmoment.

## Spulenpaare ermitteln

1. Motor vom Board abstecken.
2. Mit dem Multimeter im Widerstands- oder Durchgangsmodus zwei Kabel suchen,
   die miteinander verbunden sind. Das ist ein Spulenpaar.
3. Die beiden übrigen Kabel bilden das zweite Spulenpaar.
4. Zwischen Kabeln aus verschiedenen Spulen darf kein Durchgang messbar sein.

Beim verlinkten StepperOnline `17HE15-1504S` liegt der Spulenwiderstand laut
Datenblatt bei ca. `2,3 Ohm` pro Phase. Der genaue Messwert ist weniger wichtig
als die Zuordnung: zwei Kabel mit niedrigem Widerstand gehören zusammen.

Ohne Multimeter kann man zwei Motorleitungen kurz miteinander verbinden und die
Motorwelle von Hand drehen. Wird die Welle deutlich schwergängiger, gehören
diese zwei Leitungen zur gleichen Spule. Dieser Test ersetzt die Messung nicht,
ist aber hilfreich zur schnellen Kontrolle.

## SKR-Pico-Motorstecker

Beim SKR Pico haben die Motorstecker dieselbe Reihenfolge wie im Pinout
beschriftet. In der Ansicht des Voron/BTT-Pinouts, mit den Motorsteckern an der
oberen Boardkante, ist die Pinfolge pro Motorstecker von links nach rechts:

```text
2B | 1B | 1A | 2A
```

Damit sind die beiden mittleren Pins ein Spulenpaar (`1B`/`1A`) und die beiden
äußeren Pins das andere Spulenpaar (`2B`/`2A`). Wenn das Board in der
Anleitung gedreht dargestellt ist, nicht nach Bildrichtung arbeiten, sondern die
Beschriftung `2B 1B 1A 2A` am Pinout bzw. am Board verwenden.

## Beispiel für den verlinkten StepperOnline-Motor

StepperOnline gibt für den `17HE15-1504S` folgende Beispielbelegung an:

| Motorphase | Kabelfarbe laut Datenblatt |
|------------|----------------------------|
| `A+`       | Schwarz                    |
| `A-`       | Blau                       |
| `B+`       | Grün                       |
| `B-`       | Rot                        |

Wenn `A+`/`A-` auf die SKR-Pico-Phase `1A`/`1B` und `B+`/`B-` auf
`2A`/`2B` gelegt wird, ergibt sich am SKR-Pico-Stecker in Pinout-Reihenfolge:

```text
2B  | 1B   | 1A       | 2A
Rot | Blau | Schwarz | Grün
```

Diese Farbreihenfolge nur als Beispiel verwenden. Vor dem Einbau immer die
beiden Spulenpaare am gelieferten Motor prüfen.

## Drehrichtung prüfen

Nach dem Anschließen den Motor mit sehr kleiner Geschwindigkeit testen. Dreht
er in die falsche Richtung, ist die Spulenbelegung nicht automatisch falsch. Die
Drehrichtung kann auf zwei Arten korrigiert werden:

- in Klipper das `dir_pin` invertieren oder die Invertierung entfernen, z. B.
  `dir_pin: !gpio10`
- alternativ genau ein Spulenpaar am Stecker tauschen, also `1A` mit `1B` oder
  `2A` mit `2B`

Nicht einzelne Kabel zwischen den beiden Spulen tauschen. Das würde die
Spulenpaare wieder vermischen.

## Fehlerbilder

| Symptom | Wahrscheinliche Ursache |
|---------|--------------------------|
| Motor brummt oder vibriert nur | Spulenpaare vertauscht oder gemischt |
| Motor hat kaum Haltekraft | Ein Spulenpaar falsch angeschlossen |
| Motor dreht sauber, aber falsch herum | Drehrichtung invertieren oder ein Spulenpaar tauschen |
| Treiber oder Motor wird sofort ungewöhnlich heiß | Ausschalten und Verkabelung prüfen |
