# 🧵 String Art Generator API

Modern web interface and REST API for generating beautiful string art from images.

## Features

- **Web Interface**: Beautiful, responsive web UI with drag-and-drop image upload
- **REST API**: Full API for programmatic access
- **Command Line Client**: Terminal interface for batch processing
- **Real-time Processing**: Live progress updates and result preview
- **Multiple Formats**: Support for PNG, JPG, JPEG, GIF, BMP
- **Flexible Parameters**: Customizable nail count, iterations, strength, and more

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd string-art-api

# Install dependencies
pip install -r requirements.txt
```

### 2. Start the Server

```bash
python app.py
```

The server will start at `http://localhost:5000`

### 3. Use the Web Interface

Open your browser and go to `http://localhost:5000`

- Drag and drop an image or click to upload
- Adjust parameters as needed
- Click "Generate String Art"
- View results and download

## API Usage

### Process Image Endpoint

**POST** `/api/process`

**Parameters:**
- `image` (file): Image file to process
- `total_nails` (int): Number of nails (default: 200)
- `side_len` (int): Output size in pixels (default: 800)
- `export_strength` (float): String strength (default: 0.1)
- `pull_amount` (int): Max iterations (default: 2000)
- `random_nails` (int, optional): Use random subset of nails
- `shape_type` (string): "circle" or "rectangle" (default: "circle")
- `white_background` (boolean): Use white background (default: false)
- `rgb_mode` (boolean): RGB color mode (default: false)

**Response:**
```json
{
  "success": true,
  "output_file": "result_abc123.png",
  "nails_count": 200,
  "pull_order": "0-15-32-..."
}
```

### Download Result

**GET** `/api/download/<filename>`

Downloads the processed image file.

### View Result

**GET** `/api/view/<filename>`

Displays the processed image in browser.

## Command Line Usage

Use the included `api_client.py` for terminal access:

```bash
# Basic usage
python api_client.py -i input.jpg -o result.png

# With custom parameters
python api_client.py -i photo.jpg -o art.png --nails 300 --size 1000 --iterations 3000

# RGB mode with white background
python api_client.py -i image.png -o colored_art.png --rgb --white-bg

# Rectangle shape with verbose output
python api_client.py -i pic.jpg -o rect_art.png --shape rectangle -v
```

### Command Line Options

```
-i, --input          Input image file path (required)
-o, --output         Output file path (default: result.png)
--server             API server URL (default: http://localhost:5000)
--nails              Number of nails (default: 200)
-d, --size           Output size in pixels (default: 800)
-s, --strength       String strength (default: 0.1)
-l, --iterations     Max iterations (default: 2000)
-r, --random-nails   Use random subset of nails
--shape              Shape type: circle or rectangle (default: circle)
--white-bg           Use white background
--rgb                RGB color mode
-v, --verbose        Verbose output
```

## Parameters Explained

### Core Parameters

- **Number of Nails**: Total nails placed around the perimeter (50-1000)
- **Output Size**: Final image dimensions in pixels (300-2000)
- **String Strength**: How dark/light the strings appear (0.01-1.0)
- **Max Iterations**: Maximum number of string connections (100-10000)

### Advanced Options

- **Random Nails**: Use only a random subset of nails for faster processing
- **Shape Type**: 
  - **Circle**: Traditional circular string art
  - **Rectangle**: Rectangular frame layout
- **White Background**: 
  - **Off**: Dark strings on light background
  - **On**: Light strings on dark background
- **RGB Mode**: Generate colored string art using red, green, blue threads

## Examples

### Web Interface Examples

1. **Portrait Photo**: Use 300+ nails, 3000+ iterations for detailed results
2. **Simple Logo**: Use 150-200 nails, 1500 iterations for clean lines
3. **Landscape**: Try rectangle shape with 250 nails

### API Examples

```bash
# High quality portrait
curl -X POST -F "image=@portrait.jpg" \
     -F "total_nails=400" \
     -F "pull_amount=4000" \
     -F "side_len=1200" \
     http://localhost:5000/api/process

# Quick preview
curl -X POST -F "image=@test.png" \
     -F "total_nails=100" \
     -F "pull_amount=500" \
     http://localhost:5000/api/process
```

## Project Structure

```
string-art-api/
├── app.py                 # Flask application
├── string_art_library.py  # Core string art algorithms
├── api_client.py          # Command line client
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Web interface
├── uploads/              # Temporary uploaded files
└── outputs/              # Generated results
```

## Tips for Best Results

1. **Image Quality**: Use high-contrast images with clear subjects
2. **Nail Count**: More nails = more detail but longer processing time
3. **Iterations**: Start with 2000, increase for more detail
4. **String Strength**: Adjust based on desired contrast
5. **Shape Choice**: Circle works best for most images
6. **Processing Time**: Expect 1-5 minutes depending on parameters

## Troubleshooting

### Common Issues

**Server won't start:**
- Check if port 5000 is available
- Install all requirements: `pip install -r requirements.txt`

**Processing fails:**
- Ensure image file is valid format
- Try reducing nail count or iterations
- Check server logs for detailed errors

**Slow processing:**
- Reduce number of nails
- Lower iteration count
- Use random nails option

**Poor results:**
- Increase nail count
- Adjust string strength
- Try different shape type
- Use higher contrast source image

## Development

To modify the core algorithms, edit `string_art_library.py`. The Flask app in `app.py` imports and uses these functions.

For UI changes, modify `templates/index.html`.

## License

This project is open source. Feel free to modify and distribute. 