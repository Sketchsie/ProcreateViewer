import sys
import io
import math
import zipfile
from biplist import readPlist
import lzo
from PIL import Image
from multiprocessing import Pool


procreatefile = sys.argv[-1]
zipref = zipfile.ZipFile(procreatefile, 'r')

plistdata = zipref.read('Document.archive')
plistbytes = io.BytesIO(plistdata)
plist = readPlist(plistbytes)
objects = plist.get('$objects')
composite_number = objects[1].get('composite').integer
composite_key_number = objects[composite_number].get('UUID').integer
composite_key = objects[composite_key_number]

allfiles = zipref.namelist()
composite_files = list(filter(lambda x: composite_key in x, allfiles))
filelist = list(map(lambda x: x.strip(composite_key).strip('/'), composite_files))

imagesize_string = objects[objects[1].get('size').integer]
imagesize = imagesize_string.strip('{').strip('}').split(', ')
imagesize[0] = int(imagesize[0])
imagesize[1] = int(imagesize[1])
tilesize = objects[1].get('tileSize')
orientation = objects[1].get('orientation')
h_flipped = objects[1].get('flippedHorizontally')
v_flipped = objects[1].get('flippedVertically')
name = objects[objects[1].get('name').integer]

# create a new image
canvas = Image.new('RGBA', (imagesize[0], imagesize[1]))

# Figure out how many total rows and columns there are
columns = int(math.ceil(float(imagesize[0]) / float(tilesize)))
rows = int(math.ceil(float(imagesize[1]) / float(tilesize)))

# Calculate differencex and differencey
differencex = 0
differencey = 0
if imagesize[0] % tilesize != 0:
    differencex = (columns * tilesize) - imagesize[0]
if imagesize[1] % tilesize != 0:
    differencey = (rows * tilesize) - imagesize[1]

# iterate through chunks
# decompress them
# create images
def processChunk(filename):
    # Get row and column from filename
    column = int(filename.strip('.chunk').split('~')[0])
    row = int(filename.strip('.chunk').split('~')[1]) + 1
    chunk_tilesize = {
        "x": tilesize,
        "y": tilesize
    }

    # Account for columns or rows that are too short
    if (column + 1) == columns:
        chunk_tilesize['x'] = tilesize - differencex
    if row == rows:
        chunk_tilesize['y'] = tilesize - differencey

    # read the actual data and create an image
    file = zipref.read(composite_key + '/' + filename)
    # 262144 is the final byte size of the pixel data for 256x256 square.
    # This is based on 256*256*4 (width * height * 4 bytes per pixel)
    # finalsize is chunk width * chunk height * 4 bytes per pixel
    finalsize = chunk_tilesize['x'] * chunk_tilesize['y'] * 4
    decompressed = lzo.decompress(file, False, finalsize)
    # Will need to know how big each tile is instead of just saying 256
    tile = Image.frombytes('RGBA', (chunk_tilesize['x'],chunk_tilesize['y']), decompressed)
    # Tile starts upside down, flip it
    tile = tile.transpose(Image.FLIP_TOP_BOTTOM)

    # Calculate pixel position of tile
    positionx = column * tilesize
    positiony = (imagesize[1] - (row * tilesize))
    if (row == rows):
        positiony = 0

    return (tile, (positionx, positiony))


# for (filename) in filelist:
#   processChunk(filename)

# Same as commented out for loop above, but multi-threaded
p = Pool()
tilelist = p.map(processChunk, filelist)
p.close()
p.join()

# Add each tile to composite image
# (This won't work in the multithreaded function for some reason)
for tile in tilelist:
    canvas.paste(tile[0], tile[1])

# Make sure the image appears in the correct orientation
if orientation == 3:
    canvas = canvas.rotate(90, expand=True)
elif orientation == 4:
    canvas = canvas.rotate(-90, expand=True)
elif orientation == 2:
    canvas = canvas.rotate(180, expand=True)

if h_flipped == 1 and (orientation == 1 or orientation == 2):
    canvas = canvas.transpose(Image.FLIP_LEFT_RIGHT)
if h_flipped == 1 and (orientation == 3 or orientation == 4):
    canvas = canvas.transpose(Image.FLIP_TOP_BOTTOM)
if v_flipped == 1 and (orientation == 1 or orientation == 2):
    canvas = canvas.transpose(Image.FLIP_TOP_BOTTOM)
if v_flipped == 1 and (orientation == 3 or orientation == 4):
    canvas = canvas.transpose(Image.FLIP_LEFT_RIGHT)

# canvas.show()
canvas.save(name + ".BMP")
print("Image saved to current directory")