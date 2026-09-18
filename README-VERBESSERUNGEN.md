# Projektprüfung und Verbesserungen

Diese Überarbeitung konzentriert sich auf zuverlässige Messergebnisse,
Windows-Kompatibilität und einen nachvollziehbaren LLM-Arbeitsablauf. Untersucht
wurden Server und Hilfsmodule, Konfiguration, Cache-Verhalten, Test- und CI-Setup,
Skill-Dateien sowie die zugehörige Dokumentation. Das ist keine Garantie, dass
jedes mögliche Modell oder jede Plattform fehlerfrei funktioniert.

## Ergänzung: komplexe und variable Bauteile

Die Prüfung von Parameterreihen (`validate(mode="predicates", sweep=...)`) bezieht
jetzt alle getesteten Varianten in `valid` ein. Bisher konnte der Standardwert
bestehen und das Gesamtergebnis trotz einer fehlerhaften Variante gültig bleiben.
OpenSCAD-Fehler einzelner Varianten verhindern ebenfalls ein Bestehen; Fehler und
Warnungen enthalten den zugehörigen Parameterwert und verweisen auf das Modell.

Der Design-Skill beschreibt jetzt Grenzwertprüfungen, Kombinationen voneinander
abhängiger Parameter und separate Geometrieprüfungen. Bei Baugruppen berücksichtigt
er auch Einbauwege sowie Freiräume für Schraubendreher, Stecker und Kabel. Stichproben
einer Bewegung sind ausdrücklich kein Beweis für einen durchgehend freien Weg.

Das vorhandene Beispiel lässt sich mit
`uv run python examples/verify_skill_test.py` ausführen. Es prüft zusätzlich, ob um
die Bohrung mindestens 2 mm Material verbleiben: 5, 10 und 16 mm Bohrungsdurchmesser
bestehen, 18 mm wird bewusst abgewiesen. Die Mesh- und Renderprüfungen gelten weiter
für das Standardmodell; die Variantenprüfung bewertet hier nur die Maßbedingungen.

Beispielprompt für deine LLM:

```text
Verwende openscad-design und prüfe examples/skill_test.scad.
Teste mit validate(mode="predicates") die Bedingung
(min(width_x, depth_y) - hole_d) / 2 >= 2
für hole_d = 5, 10, 16 und 18 mittels sweep.
Nenne die abgewiesene Variante und den verbleibenden Materialsteg.
Prüfe anschließend die Variante hole_d=16 separat mit measure und
validate(mode="geometry"), jeweils mit variables={"hole_d": 16}.
Rendere diese Variante erst nach bestandenen Geometrieprüfungen.
```

## Was verbessert wurde

Die oben beschriebene Ergänzung wurde mit **151 bestandenen Tests und einem
übersprungenen Test** in den Gruppen Geometrie-Werkzeuge, Baugruppen-Checks und
Korrekturtests geprüft. Dazu gehören fünf neue Regressionstests. Das ausführbare
OpenSCAD-Beispiel, Lint (`F,E9,B`) und die Skill-Validierung waren ebenfalls erfolgreich.

| Bereich | Problem | Änderung |
|---|---|---|
| Render-Cache | Änderungen bei identischer Größe und identischem Zeitstempel konnten unentdeckt bleiben. | Abhängigkeiten werden anhand ihres SHA-256-Inhalts geprüft. |
| Mess- und Teile-Cache | Statische Abhängigkeiten wurden nur über Dateistatistik identifiziert. | Inhaltsbasierte Fingerprints; auch die Hauptdatei des Mess-Cache wird inhaltlich erfasst. |
| Cache leeren | Messungen und geladene Meshes blieben im Arbeitsspeicher. | `clear_cache` leert zusätzlich beide Speicher-Caches, auch ohne vorhandenes Cache-Verzeichnis. |
| Cache deaktivieren | Der Mess-Cache wurde unabhängig von `MCP_CACHE_ENABLED` benutzt. | Deaktivierte Mess-Caches werden weder gelesen noch neu befüllt. |
| Windows und Unicode | SCAD, Wrapper, YAML und Prozessausgaben verwendeten teils die lokale Zeichenkodierung. | Explizites UTF-8; BOM-Unterstützung beim Lesen von Modellen und YAML; UTF-8-Logdateien. |
| Tempverzeichnis | Der Standard `/tmp/openscad-mcp` war auf Windows ungeeignet. | Betriebssystemabhängiges Tempverzeichnis über `tempfile.gettempdir()`. |
| Konfigurationsdateien | Leere YAML-Dateien und falsche Wurzeltypen führten zu wenig hilfreichen Fehlern. | Leere Dateien verwenden Standardwerte; Listen und Skalare werden verständlich abgewiesen. |
| Tests | Pfadvergleiche setzten Linux-Schreibweise voraus. | Vergleiche mit `Path`, zusätzliche Regressionstests und Windows-CI. |
| Testkonfiguration | Optionen für ein nicht installiertes Timeout-Plugin und ein unbestimmter Async-Fixture-Scope. | Unwirksame Timeout-Optionen aus der aktiven Konfiguration entfernt, Scope ausdrücklich gesetzt. |
| Kaufteiltests | OpenSCAD war vorhanden, BOSL2 fehlte: irreführende Geometriefehler. | Bibliotheksprüfung durch OpenSCAD; fehlendes BOSL2 führt zu einem begründeten Skip. |
| Kaufteil-Prüfprozess | Der Windows-Konsolenstarter konnte unter pytest ohne brauchbare Ausgabe enden. | Standardeingabe auf `DEVNULL` setzen und Diagnoseausgaben aus beiden Ausgabekanälen berücksichtigen. |
| Linter | Veraltete Ruff-Konfigurationsstruktur erzeugte Warnungen. | Regeln unter `tool.ruff.lint` eingeordnet. |
| Skill | Kritische Hardwaremaße konnten geraten und CSG-Cutter als fertige Bohrungen interpretiert werden. | Fehlende kritische Maße erfragen; CSG-Features, Mesh-Komponenten und benannte Teile präzise unterscheiden. |
| Dokumentation | Cache-Größenlimit und Tempverzeichnis waren teils falsch beschrieben. | README, API, Deployment, Agentenhinweise und `.env.example` aktualisiert. |

Das Hashen verursacht zusätzliche Dateilesezugriffe. Dieser Aufwand verhindert
veraltete Messergebnisse und ist normalerweise deutlich kleiner als ein erneuter
OpenSCAD-Export. Eine allgemeine Beschleunigung wird damit nicht behauptet.

Die bereits vorhandene Überarbeitung des Skills bleibt erhalten: ein kompakter
Hauptablauf und zwei bedarfsgerecht geladene Referenzen. Für die Skill-Anpassungen
wurden die Strukturregeln aus `skill-creator` angewendet.

## Beispiel: Quader mit Durchgangsbohrung

Das vollständige Modell liegt in [examples/skill_test.scad](examples/skill_test.scad).
Es erzeugt einen Quader mit 30 × 20 × 10 mm, einer zentrierten 5-mm-Bohrung und
dem Ursprung mittig auf der Unterseite. Die Rundungsauflösung gilt nur für den
Bohrungszylinder; `eps` verlängert den Cutter über beide Außenflächen.

```openscad
width_x = 30;
depth_y = 20;
height_z = 10;
hole_d = 5;
hole_fn = 64;
eps = 0.01;

difference() {
    translate([-width_x/2, -depth_y/2, 0])
        cube([width_x, depth_y, height_z]);
    translate([0, 0, -eps])
        cylinder(d=hole_d, h=height_z + 2*eps, $fn=hole_fn);
}
```

Mit installiertem OpenSCAD im Projektverzeichnis ausführen:

```powershell
uv sync --extra dev
uv run python examples/verify_skill_test.py
```

Das Prüfskript führt die Serverfunktionen für Syntaxprüfung, Parameterauswertung,
Messung, Feature-Analyse, Geometrieprüfung und orthografisches Rendern aus. Es prüft
Sollwerte und endet bei Abweichungen mit einem Fehler. Temporäre Dateien werden
aufgeräumt; es entsteht kein dauerhafter STL-/3MF-Export.

Im lokalen Lauf mit OpenSCAD 2021.01 wurden bestätigt:

- Abmessungen: 30 × 20 × 10 mm
- Bounding Box: `[-15, -10, 0]` bis `[15, 10, 10]`
- ein geschlossener, manifold Körper
- Volumen: ungefähr 5803,96585 mm³
- nominaler Cutterdurchmesser: 5 mm, kleinster polygonaler Durchmesser: 4,994 mm
- erfolgreiches Rendern ohne gemeldete Fehler oder Warnungen

Das Volumen wird gegen den 64-seitigen Bohrungscutter geprüft. Der analytische Kreis
hätte ein etwas anderes Volumen. `features.through` ist `null`: Die Feature-Ausgabe
allein bestätigt keine fertige Durchgangsbohrung. In diesem einfachen Beispiel
stützen Quellgeometrie, Bounding Box und Volumenprüfung die Interpretation.

## Verwendung mit DeepSeek und einem MCP-Client

Die MCP-Verbindung stellt Werkzeuge bereit. Damit die LLM den Design-Skill laden
kann, muss zusätzlich der komplette Ordner `skills/openscad-design` im Client
registriert sein, einschließlich `references/`.

Im getesteten OpenCode-Projekt liegt die Kopie unter
`.opencode/skills/openscad-design/`. Änderungen in diesem Repository aktualisieren
diese Kopie nicht automatisch. Synchronisiere sie vor einem neuen Test. Bei Clients
ohne Skill-Unterstützung können die Dateien als Kontext angehängt werden.

Beispielprompt:

```text
Lade den Skill openscad-design. Wenn er nicht verfügbar ist, melde das zuerst.

Prüfe examples/skill_test.scad mit OpenSCAD-MCP:
1. validate(mode="syntax")
2. scad_eval für width_x, depth_y, height_z und hole_d
3. measure(mode="model") und measure(mode="features")
4. validate(mode="geometry")
5. render(grounded=true) in einer isometrischen Ansicht

Erwartet werden 30 × 20 × 10 mm, eine zentrierte Bohrung entlang Z und
ein geschlossener, manifold Körper. Nenne die tatsächlichen Messwerte,
Warnungen und Grenzen der Prüfung. Erzeuge keinen finalen Mesh-Export.
```

Der Tool-Verlauf muss das Laden des Skills und echte Werkzeugaufrufe zeigen.
Das Python-Prüfskript prüft den Serverablauf, nicht das Verhalten oder die
Skill-Registrierung eines bestimmten LLM-Clients.

## Prüfungen und Grenzen

Abschlusslauf unter Windows, Python 3.12.10 und OpenSCAD 2021.01:

- Hauptsuite: **1514 bestanden, 32 übersprungen**, 24 Performance-Tests separat ausgewählt.
- Coverage: **88,47 %**, Mindestanforderung 80 % erfüllt.
- Performance-Gruppe: **23 bestanden, 1 übersprungen**.
- Projekt-Lint (`F,E9,B`), Skill-Validator und lokale Dokumentationslinks: bestanden.
- Echtes OpenSCAD-Prüfbeispiel sowie Bau von Wheel und Quellpaket: bestanden.
- BOSL2 ist lokal nicht installiert; entsprechende Geometrietests wurden nicht ausgeführt.

Regressionstests decken Änderungen mit erhaltenem Zeitstempel, Unicode-Dateien,
YAML-Konfiguration und Speicher-Caches ab. Die vorhandene Testsuite deckt außerdem
Geometrie, Kamera, Baugruppen, Druckbarkeit, Katalog, Export und MCP-Werkzeuge ab.

```powershell
uv run pytest -q -p no:cacheprovider -m "not performance"
uv run ruff check --select F,E9,B src/openscad_mcp/
```

Für die echte Geometrie-Testgruppe muss OpenSCAD im `PATH` liegen. Die Kaufteiltests
benötigen zusätzlich BOSL2. Ohne diese Abhängigkeiten werden betreffende Tests
übersprungen; dadurch kann die vorgeschriebene 80-%-Coverage unterschritten werden.
Die Linux-CI mit beiden Abhängigkeiten behält dieses Qualitätskriterium bei.
Die zusätzliche Windows-CI prüft die portable Suite ohne Coverage-Schwelle.

Statische Cache-Abhängigkeiten können berechnete Import-Dateinamen nicht vollständig
auflösen. Nach Änderungen solcher Daten `clear_cache` aufrufen. Die Überarbeitung
fügt keine Festigkeitsberechnung hinzu und verifiziert keine unbekannten Maße realer
Hardware. Nicht lokal ausgeführte Plattform- und Bibliothekstests bleiben offen.
