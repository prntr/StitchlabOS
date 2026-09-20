# PicturetoStichlab Report

PicturetoStichlab is an add-on pipeline that turns images into embroidery-ready G-code for StitchLAB. Two prototype stages target the same goal, with different levels of automation and fidelity. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/main.py; /Users/boxer/Code/active/IMG2SVG2SITCH/img2svg.py; /Users/boxer/Code/active/IMG2SVG2SITCH/svg2embroidery.py)

## 1) Goal and scope

Goal: capture or import an image, vectorize it into SVG, convert to stitches, and run on a Klipper-based embroidery machine. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/camera/routes.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/vector/vectorize.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/converter.py; /Users/boxer/Code/active/IMG2SVG2SITCH/svg2embroidery.py)

## 2) Stage A: RPIcam2Embroidery (camera + web + Moonraker)

Pipeline: **Camera -> Vectorize -> Digitize -> G-code -> Moonraker upload**. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/camera/capture.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/vector/vectorize.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/converter.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/gcode_generator.py)

Key components:
- **Backend API (Flask):** `/api/camera/capture`, `/api/embroidery/preview`, `/api/embroidery/convert-and-upload`. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/main.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/camera/routes.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/preview.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/controller.py)
- **Camera capture:** Picamera2 + PIL, default 1920x1080, saved to `uploads/`. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/camera/capture.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/config/config.py)
- **Vectorization:** threshold + optional morphology + speck removal + Potrace tracing. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/vector/vectorize.py)
- **Embroidery conversion:** python-embroidery digitizer with fill/satin strategies; outputs a stitch plan and DST. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/converter.py)
- **G-code:** `G1 X/Y` and `G1 Z` with 5.0 mm per stitch, uploaded to Moonraker `/server/files/upload`. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/gcode_generator.py)
- **Frontend:** Vue app that previews SVG bounds, sets offset/scale, and triggers conversion/upload. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/frontend/src/App.vue)

Known gaps:
- `requirements.txt` does not list Potrace or python-embroidery though both are imported. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/requirements.txt; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/vector/vectorize.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/converter.py)
- Some modules are placeholders (`enhance.py`, `klipper_connection.py`, `frontend/optimize.py`). (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/image_processing/enhance.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/utils/klipper_connection.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/frontend/optimize.py)

## 3) Stage B: IMG2SVG2SITCH (CLI, high-fidelity SVG)

Pipeline: **Image -> SVG -> G-code** using two scripts. (source: /Users/boxer/Code/active/IMG2SVG2SITCH/img2svg.py; /Users/boxer/Code/active/IMG2SVG2SITCH/svg2embroidery.py)

Key components:
- **img2svg.py:** image thresholding (optionally Otsu), Potrace tracing, RDP simplification, containment classification, union/difference cleanup, SVG output. (source: /Users/boxer/Code/active/IMG2SVG2SITCH/img2svg.py)
- **svg2embroidery.py:** outline/fill/both modes, canvas scaling, preview rendering, `G0` moves with configurable Z increment (default 5.0 mm). (source: /Users/boxer/Code/active/IMG2SVG2SITCH/svg2embroidery.py)
- **Output:** writes G-code and optional preview image to disk. (source: /Users/boxer/Code/active/IMG2SVG2SITCH/svg2embroidery.py)

## 4) Comparison and how they align

- **Entry point:** RPIcam2Embroidery is a live camera + web UI workflow; IMG2SVG2SITCH is an offline CLI pipeline for higher-quality SVG generation. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/main.py; /Users/boxer/Code/active/IMG2SVG2SITCH/img2svg.py)
- **Vectorization depth:** IMG2SVG2SITCH adds Otsu, RDP simplification, and polygon cleanup beyond the current RPIcam2Embroidery pipeline. (source: /Users/boxer/Code/active/IMG2SVG2SITCH/img2svg.py; /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/vector/vectorize.py)
- **Embroidery logic:** RPIcam2Embroidery uses python-embroidery digitization; IMG2SVG2SITCH samples paths directly for G-code. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/converter.py; /Users/boxer/Code/active/IMG2SVG2SITCH/svg2embroidery.py)
- **Moonraker/Klipper:** RPIcam2Embroidery uploads via Moonraker API; IMG2SVG2SITCH outputs files for manual upload or later automation. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/gcode_generator.py; /Users/boxer/Code/active/IMG2SVG2SITCH/svg2embroidery.py)

## 5) Integration path into StitchLAB

1. Run RPIcam2Embroidery on the StitchLAB dev Pi as a local service. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/main.py)
2. Keep Moonraker upload as the delivery path so G-code lands in the standard `gcodes` folder and appears in Mainsail. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/backend/app/embroidery/gcode_generator.py)
3. Add a Mainsail entry point that opens the camera-to-embroidery UI or triggers the API. (source: /Users/boxer/Code/active/RPIcam2Embroidery/embroidery-converter/frontend/src/App.vue)
4. Optionally replace the vectorization step with IMG2SVG2SITCH's higher-fidelity SVG output as a preprocessing stage. (source: /Users/boxer/Code/active/IMG2SVG2SITCH/img2svg.py)
