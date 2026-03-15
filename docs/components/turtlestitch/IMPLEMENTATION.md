# TurtleStitch StitchLAB Integration Implementation

## Overview

Added seamless integration between TurtleStitch and StitchLAB's Moonraker file storage, allowing projects to be saved to and loaded from the Pi directly through the TurtleStitch UI.

## Changes Made

### File Modified
- `turtlestitch/src/gui.js`

### Key Components Added

#### 1. Moonraker Availability Detection
```javascript
IDE_Morph.prototype.checkStitchLabAvailability()
```
- Checks if Moonraker is available on port 7125
- 1-second timeout for fast failure
- Sets `ide.stitchlabAvailable` flag
- Called automatically when opening ProjectDialogMorph

#### 2. StitchLAB Source Button
- **Label:** "StitchLAB"
- **Icon:** 'file' (file/document symbol)
- **Visibility:** Only appears if `ide.stitchlabAvailable === true`
- Added to ProjectDialogMorph.buildContents()

#### 3. Project Management Methods

**List Projects:**
```javascript
ProjectDialogMorph.prototype.getStitchLabProjectList(callback, errorCallback)
```
- Fetches from `/server/files/directory?path=gcodes/turtlestitch_projects`
- Returns sorted list (newest first)
- Filters for `.xml` files only

**Install Project List:**
```javascript
ProjectDialogMorph.prototype.installStitchLabProjectList(projects)
```
- Creates ListMorph with project names
- Sets up preview loading on selection
- Shows delete button, hides cloud-related buttons

**Load Preview:**
```javascript
ProjectDialogMorph.prototype.loadStitchLabProjectPreview(item)
```
- Fetches project XML from Pi
- Extracts and displays thumbnail
- Shows project notes in preview pane

**Save Project:**
```javascript
ProjectDialogMorph.prototype.saveStitchLabProject()
```
- Serializes current project to XML
- Uploads via FormData POST to `/server/files/upload`
- Uses `root=gcodes`, `path=turtlestitch_projects`
- Shows success/error messages

**Open Project:**
```javascript
ProjectDialogMorph.prototype.openStitchLabProject(proj)
```
- Downloads project XML from Pi
- Calls IDE's openProjectString()
- Includes backup before opening

**Add Scene:**
```javascript
ProjectDialogMorph.prototype.addStitchLabScene(proj)
```
- Downloads project XML
- Adds as new scene to current project
- Uses IDE's scene management

**Delete Project:**
- Extended `ProjectDialogMorph.prototype.deleteProject()`
- Added `else if (this.source === 'stitchlab')` case
- Uses DELETE request to `/server/files/gcodes/turtlestitch_projects/{filename}`
- Refreshes list after deletion

#### 4. Source Selection Handler

Extended `ProjectDialogMorph.prototype.setSource()` switch statement:
```javascript
case 'stitchlab':
    msg = this.ide.showMessage('Updating\\nproject list...');
    this.getStitchLabProjectList(
        projects => {
            if (this.source === 'stitchlab') {
                this.installStitchLabProjectList(projects);
            }
            msg.destroy();
        },
        err => {
            msg.destroy();
            this.ide.showMessage('StitchLAB Error: ' + err, 3);
        }
    );
    return;
```

#### 5. Save Handler

Extended `ProjectDialogMorph.prototype.saveProject()`:
```javascript
else if (this.source === 'stitchlab') {
    if (detect(this.projectList, item => item.filename === name + '.xml')) {
        // Confirm overwrite
        this.ide.confirm(...);
    } else {
        this.ide.setProjectName(name);
        this.saveStitchLabProject();
    }
}
```

## User Flow

### Saving to StitchLAB
1. User clicks **File → Save As...**
2. ProjectDialog opens
3. If Moonraker available, **StitchLAB** button visible
4. User clicks **StitchLAB** button
5. Project list loads from Pi (if available)
6. User enters project name
7. If name exists, confirmation prompt appears
8. User clicks **Save**
9. Project uploads to `/home/pi/printer_data/gcodes/turtlestitch_projects/`
10. Success message shown

### Loading from StitchLAB
1. User clicks **File → Open**
2. ProjectDialog opens with **StitchLAB** button (if available)
3. User clicks **StitchLAB** button
4. Project list fetches and displays (sorted newest first)
5. User clicks on a project name
6. Preview loads (thumbnail + notes)
7. User clicks **Open**
8. Project downloads and opens
9. IDE source set to 'stitchlab'

### Deleting from StitchLAB
1. User opens project dialog
2. Clicks **StitchLAB** source
3. Selects a project from list
4. Clicks **Delete** button
5. Confirms deletion
6. Project deleted from Pi
7. List refreshes

## API Endpoints Used

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Check availability | GET | `/server/info` |
| List projects | GET | `/server/files/directory?path=gcodes/turtlestitch_projects` |
| Download project | GET | `/server/files/gcodes/turtlestitch_projects/{filename}` |
| Upload project | POST | `/server/files/upload` (FormData with root, path, file) |
| Delete project | DELETE | `/server/files/gcodes/turtlestitch_projects/{filename}` |

## Error Handling

- **Moonraker unavailable:** StitchLAB button doesn't appear
- **Network timeout:** 2-second timeout on availability check
- **Load failure:** Error message displayed, operation aborted
- **Save failure:** Error message shown, dialog remains open
- **Delete failure:** Error message, list not refreshed

## File Format

Projects saved as XML files with `.xml` extension:
- Filename: `{projectName}.xml`
- Contains full TurtleStitch/Snap! project structure
- Includes thumbnail, notes, sprites, costumes, blocks, etc.

## Testing

1. Open http://stitchlabdev.local:3000
2. Create a simple drawing
3. File → Save As...
4. Click StitchLAB button (file icon)
5. Enter name, click Save
6. Verify success message
7. File → New (don't save)
8. File → Open
9. Click StitchLAB button
10. Select saved project
11. Verify it loads correctly

## Future Enhancements

- [ ] Project tags/metadata
- [ ] Subfolder organization
- [ ] Bulk operations (export all, import multiple)
- [ ] Search/filter in project list
- [ ] Project sharing between users
- [ ] Version history/snapshots
- [ ] Auto-save to StitchLAB
- [ ] Conflict resolution for concurrent edits
- [ ] TurtleStitch cloud access via Pi (nginx reverse proxy to upstream cloud with same-origin cookies, update `snap-cloud-domain` meta)
