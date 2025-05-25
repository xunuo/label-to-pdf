from flask import Flask, request, jsonify, render_template, send_file
import os
import uuid
from werkzeug.utils import secure_filename
import numpy as np
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from string_art_library import (
    rgb2gray, largest_square, create_rectangle_nail_positions, 
    create_circle_nail_positions, init_canvas, create_art, 
    scale_nails, pull_order_to_array_bw, pull_order_to_array_rgb,
    convert_pull_order_to_colored, get_quadrant_colors, get_quadrant_positions
)
from skimage.transform import resize
import io
import base64
import threading
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Progress tracking
progress_data = {}

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_string_art(image_path, params):
    """Process string art with given parameters"""
    try:
        # Load and preprocess image
        img = mpimg.imread(image_path)
        
        if np.any(img > 100):
            img = img / 255
        
        # Make square and resize
        img = largest_square(img)
        img = resize(img, (300, 300))
        
        shape = (len(img), len(img[0]))
        
        # Create nails
        if params.get('shape_type') == 'rectangle':
            nails = create_rectangle_nail_positions(shape, params['total_nails'])
        else:
            nails = create_circle_nail_positions(shape, params['total_nails'])
        
        # Generate unique output filename
        output_filename = f"result_{uuid.uuid4().hex}.png"
        instructions_filename = f"instructions_{uuid.uuid4().hex}.txt"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        instructions_path = os.path.join(app.config['OUTPUT_FOLDER'], instructions_filename)
        
        if params.get('rgb_mode'):
            # RGB mode
            iteration_strength = 0.1 if params.get('white_background') else -0.1
            
            r = img[:,:,0]
            g = img[:,:,1] 
            b = img[:,:,2]
            
            str_pic_r = init_canvas(shape, black=not params.get('white_background'))
            pull_orders_r = create_art(nails, r, str_pic_r, iteration_strength, i_limit=params.get('pull_amount'), random_nails=params.get('random_nails'))
            
            str_pic_g = init_canvas(shape, black=not params.get('white_background'))
            pull_orders_g = create_art(nails, g, str_pic_g, iteration_strength, i_limit=params.get('pull_amount'), random_nails=params.get('random_nails'))
            
            str_pic_b = init_canvas(shape, black=not params.get('white_background'))
            pull_orders_b = create_art(nails, b, str_pic_b, iteration_strength, i_limit=params.get('pull_amount'), random_nails=params.get('random_nails'))
            
            max_pulls = np.max([len(pull_orders_r), len(pull_orders_g), len(pull_orders_b)])
            pull_orders_r = pull_orders_r + [pull_orders_r[-1]] * (max_pulls - len(pull_orders_r))
            pull_orders_g = pull_orders_g + [pull_orders_g[-1]] * (max_pulls - len(pull_orders_g))
            pull_orders_b = pull_orders_b + [pull_orders_b[-1]] * (max_pulls - len(pull_orders_b))
            
            pull_orders = [pull_orders_r, pull_orders_g, pull_orders_b]
            
            color_image_dimens = params['side_len'], params['side_len'], 3
            blank = init_canvas(color_image_dimens, black=not params.get('white_background'))
            
            scaled_nails = scale_nails(
                color_image_dimens[1] / shape[1],
                color_image_dimens[0] / shape[0],
                nails
            )
            
            result = pull_order_to_array_rgb(
                pull_orders,
                blank,
                scaled_nails,
                (np.array((1., 0., 0.,)), np.array((0., 1., 0.,)), np.array((0., 0., 1.,))),
                -abs(params['export_strength']) if params.get('white_background') else abs(params['export_strength'])
            )
            
            pull_order_str = f"R:{'-'.join([str(idx) for idx in pull_orders_r[:100]])}"
            
            # Generate colored instructions for circle mode
            if params.get('shape_type') == 'circle':
                colored_instructions = convert_pull_order_to_colored(pull_orders_r, params['total_nails'])
                pull_order_str = ' | '.join(colored_instructions[:20])  # Show first 20 instructions
                
                # Save full instructions to text file
                with open(instructions_path, 'w', encoding='utf-8') as f:
                    f.write(f"String Art Instructions\n")
                    f.write(f"======================\n\n")
                    f.write(f"Parameters:\n")
                    f.write(f"- Total Nails: {params['total_nails']}\n")
                    f.write(f"- Shape: {params.get('shape_type', 'circle')}\n")
                    f.write(f"- Output Size: {params['side_len']}px\n")
                    f.write(f"- String Strength: {params['export_strength']}\n")
                    f.write(f"- Max Iterations: {params.get('pull_amount', 'unlimited')}\n")
                    f.write(f"- Random Nails: {params.get('random_nails', 'all')}\n")
                    f.write(f"- White Background: {params.get('white_background', False)}\n\n")
                    f.write(f"Quadrant Layout:\n")
                    f.write(f"- Blue: 12 o'clock (indices 150-199)\n")
                    f.write(f"- Red: 3 o'clock (indices 0-49)\n")
                    f.write(f"- Green: 6 o'clock (indices 50-99)\n")
                    f.write(f"- Yellow: 9 o'clock (indices 100-149)\n\n")
                    f.write(f"Instructions ({len(colored_instructions)} total):\n")
                    f.write(f"{'='*50}\n")
                    for i, instruction in enumerate(colored_instructions, 1):
                        f.write(f"{i:4d}. {instruction}\n")
            else:
                pull_order_str = '-'.join([str(idx) for idx in pull_orders_r[:100]])
                
                # Save rectangle instructions to text file
                with open(instructions_path, 'w', encoding='utf-8') as f:
                    f.write(f"String Art Instructions\n")
                    f.write(f"======================\n\n")
                    f.write(f"Parameters:\n")
                    f.write(f"- Total Nails: {params['total_nails']}\n")
                    f.write(f"- Shape: {params.get('shape_type', 'circle')}\n")
                    f.write(f"- Output Size: {params['side_len']}px\n")
                    f.write(f"- String Strength: {params['export_strength']}\n")
                    f.write(f"- Max Iterations: {params.get('pull_amount', 'unlimited')}\n")
                    f.write(f"- Random Nails: {params.get('random_nails', 'all')}\n")
                    f.write(f"- White Background: {params.get('white_background', False)}\n\n")
                    f.write(f"Pull Order ({len(pull_orders_r)} total):\n")
                    f.write(f"{'='*30}\n")
                    for i, nail_idx in enumerate(pull_orders_r, 1):
                        f.write(f"{i:4d}. Nail {nail_idx}\n")
        
        else:
            # Black and white mode
            orig_pic = rgb2gray(img) * 0.9
            
            image_dimens = params['side_len'], params['side_len']
            
            if params.get('white_background'):
                str_pic = init_canvas(shape, black=False)  # Start with white canvas
                pull_order = create_art(nails, orig_pic, str_pic, -0.05, i_limit=params.get('pull_amount'), random_nails=params.get('random_nails'))
                blank = init_canvas(image_dimens, black=False)  # White background
            else:
                str_pic = init_canvas(shape, black=True)   # Start with black canvas
                pull_order = create_art(nails, orig_pic, str_pic, 0.05, i_limit=params.get('pull_amount'), random_nails=params.get('random_nails'))
                blank = init_canvas(image_dimens, black=True)   # Black background
            
            scaled_nails = scale_nails(
                image_dimens[1] / shape[1],
                image_dimens[0] / shape[0],
                nails
            )
            
            result = pull_order_to_array_bw(
                pull_order,
                blank,
                scaled_nails,
                -abs(params['export_strength']) if params.get('white_background') else abs(params['export_strength'])
            )
            
            # Generate colored instructions for circle mode
            if params.get('shape_type') == 'circle':
                colored_instructions = convert_pull_order_to_colored(pull_order, params['total_nails'])
                pull_order_str = ' | '.join(colored_instructions[:20])  # Show first 20 instructions
                
                # Save full instructions to text file
                with open(instructions_path, 'w', encoding='utf-8') as f:
                    f.write(f"String Art Instructions\n")
                    f.write(f"======================\n\n")
                    f.write(f"Parameters:\n")
                    f.write(f"- Total Nails: {params['total_nails']}\n")
                    f.write(f"- Shape: {params.get('shape_type', 'circle')}\n")
                    f.write(f"- Output Size: {params['side_len']}px\n")
                    f.write(f"- String Strength: {params['export_strength']}\n")
                    f.write(f"- Max Iterations: {params.get('pull_amount', 'unlimited')}\n")
                    f.write(f"- Random Nails: {params.get('random_nails', 'all')}\n")
                    f.write(f"- White Background: {params.get('white_background', False)}\n\n")
                    f.write(f"Quadrant Layout:\n")
                    f.write(f"- Blue: 12 o'clock (indices 150-199)\n")
                    f.write(f"- Red: 3 o'clock (indices 0-49)\n")
                    f.write(f"- Green: 6 o'clock (indices 50-99)\n")
                    f.write(f"- Yellow: 9 o'clock (indices 100-149)\n\n")
                    f.write(f"Instructions ({len(colored_instructions)} total):\n")
                    f.write(f"{'='*50}\n")
                    for i, instruction in enumerate(colored_instructions, 1):
                        f.write(f"{i:4d}. {instruction}\n")
            else:
                pull_order_str = '-'.join([str(idx) for idx in pull_order[:100]])
                
                # Save rectangle instructions to text file
                with open(instructions_path, 'w', encoding='utf-8') as f:
                    f.write(f"String Art Instructions\n")
                    f.write(f"======================\n\n")
                    f.write(f"Parameters:\n")
                    f.write(f"- Total Nails: {params['total_nails']}\n")
                    f.write(f"- Shape: {params.get('shape_type', 'circle')}\n")
                    f.write(f"- Output Size: {params['side_len']}px\n")
                    f.write(f"- String Strength: {params['export_strength']}\n")
                    f.write(f"- Max Iterations: {params.get('pull_amount', 'unlimited')}\n")
                    f.write(f"- Random Nails: {params.get('random_nails', 'all')}\n")
                    f.write(f"- White Background: {params.get('white_background', False)}\n\n")
                    f.write(f"Pull Order ({len(pull_order)} total):\n")
                    f.write(f"{'='*30}\n")
                    for i, nail_idx in enumerate(pull_order, 1):
                        f.write(f"{i:4d}. Nail {nail_idx}\n")
        
        # Save result
        mpimg.imsave(output_path, result, cmap=plt.get_cmap("gray"), vmin=0.0, vmax=1.0)
        
        # Debug info
        print(f"Result shape: {result.shape}")
        print(f"Result min/max: {result.min():.3f}/{result.max():.3f}")
        print(f"Pull order length: {len(pull_order) if 'pull_order' in locals() else 'RGB mode'}")
        print(f"Export strength used: {-abs(params['export_strength']) if params.get('white_background') else abs(params['export_strength'])}")
        print(f"White background: {params.get('white_background')}")
        
        return {
            'success': True,
            'output_file': output_filename,
            'instructions_file': instructions_filename,
            'nails_count': len(nails),
            'pull_order': pull_order_str
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def process_string_art_async(image_path, params, task_id):
    """Process string art asynchronously with progress tracking"""
    try:
        def update_progress(progress, message):
            progress_data[task_id] = {
                'progress': progress,
                'message': message,
                'status': 'processing'
            }
        
        # Initialize progress
        update_progress(0, "Loading image...")
        
        # Load and preprocess image
        img = mpimg.imread(image_path)
        
        if np.any(img > 100):
            img = img / 255
        
        # Make square and resize
        img = largest_square(img)
        img = resize(img, (300, 300))
        
        shape = (len(img), len(img[0]))
        
        update_progress(5, "Creating nail positions...")
        
        # Create nails
        if params.get('shape_type') == 'rectangle':
            nails = create_rectangle_nail_positions(shape, params['total_nails'])
        else:
            nails = create_circle_nail_positions(shape, params['total_nails'])
        
        # Generate unique output filename
        output_filename = f"result_{uuid.uuid4().hex}.png"
        instructions_filename = f"instructions_{uuid.uuid4().hex}.txt"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        instructions_path = os.path.join(app.config['OUTPUT_FOLDER'], instructions_filename)
        
        if params.get('rgb_mode'):
            update_progress(10, "Processing RGB channels...")
            # RGB mode
            iteration_strength = 0.1 if params.get('white_background') else -0.1
            
            r = img[:,:,0]
            g = img[:,:,1] 
            b = img[:,:,2]
            
            # Process each channel with progress
            update_progress(15, "Processing red channel...")
            str_pic_r = init_canvas(shape, black=params.get('white_background'))
            pull_orders_r = create_art(nails, r, str_pic_r, iteration_strength, 
                                     i_limit=params.get('pull_amount'), 
                                     random_nails=params.get('random_nails'),
                                     progress_callback=lambda p, m: update_progress(15 + p*0.25, f"Red: {m}"))
            
            update_progress(40, "Processing green channel...")
            str_pic_g = init_canvas(shape, black=params.get('white_background'))
            pull_orders_g = create_art(nails, g, str_pic_g, iteration_strength, 
                                     i_limit=params.get('pull_amount'), 
                                     random_nails=params.get('random_nails'),
                                     progress_callback=lambda p, m: update_progress(40 + p*0.25, f"Green: {m}"))
            
            update_progress(65, "Processing blue channel...")
            str_pic_b = init_canvas(shape, black=params.get('white_background'))
            pull_orders_b = create_art(nails, b, str_pic_b, iteration_strength, 
                                     i_limit=params.get('pull_amount'), 
                                     random_nails=params.get('random_nails'),
                                     progress_callback=lambda p, m: update_progress(65 + p*0.25, f"Blue: {m}"))
            
            update_progress(90, "Combining RGB channels...")
            
            max_pulls = np.max([len(pull_orders_r), len(pull_orders_g), len(pull_orders_b)])
            pull_orders_r = pull_orders_r + [pull_orders_r[-1]] * (max_pulls - len(pull_orders_r))
            pull_orders_g = pull_orders_g + [pull_orders_g[-1]] * (max_pulls - len(pull_orders_g))
            pull_orders_b = pull_orders_b + [pull_orders_b[-1]] * (max_pulls - len(pull_orders_b))
            
            pull_orders = [pull_orders_r, pull_orders_g, pull_orders_b]
            
            color_image_dimens = params['side_len'], params['side_len'], 3
            blank = init_canvas(color_image_dimens, black=params.get('white_background'))
            
            scaled_nails = scale_nails(
                color_image_dimens[1] / shape[1],
                color_image_dimens[0] / shape[0],
                nails
            )
            
            result = pull_order_to_array_rgb(
                pull_orders,
                blank,
                scaled_nails,
                (np.array((1., 0., 0.,)), np.array((0., 1., 0.,)), np.array((0., 0., 1.,))),
                params['export_strength'] if params.get('white_background') else -params['export_strength']
            )
            
            pull_order_str = f"R:{'-'.join([str(idx) for idx in pull_orders_r[:100]])}"
            
            # Generate colored instructions for circle mode
            if params.get('shape_type') == 'circle':
                colored_instructions = convert_pull_order_to_colored(pull_orders_r, params['total_nails'])
                pull_order_str = ' | '.join(colored_instructions[:20])  # Show first 20 instructions
                
                # Save full instructions to text file
                with open(instructions_path, 'w', encoding='utf-8') as f:
                    f.write(f"String Art Instructions\n")
                    f.write(f"======================\n\n")
                    f.write(f"Parameters:\n")
                    f.write(f"- Total Nails: {params['total_nails']}\n")
                    f.write(f"- Shape: {params.get('shape_type', 'circle')}\n")
                    f.write(f"- Output Size: {params['side_len']}px\n")
                    f.write(f"- String Strength: {params['export_strength']}\n")
                    f.write(f"- Max Iterations: {params.get('pull_amount', 'unlimited')}\n")
                    f.write(f"- Random Nails: {params.get('random_nails', 'all')}\n")
                    f.write(f"- White Background: {params.get('white_background', False)}\n\n")
                    f.write(f"Quadrant Layout:\n")
                    f.write(f"- Blue: 12 o'clock (indices 150-199)\n")
                    f.write(f"- Red: 3 o'clock (indices 0-49)\n")
                    f.write(f"- Green: 6 o'clock (indices 50-99)\n")
                    f.write(f"- Yellow: 9 o'clock (indices 100-149)\n\n")
                    f.write(f"Instructions ({len(colored_instructions)} total):\n")
                    f.write(f"{'='*50}\n")
                    for i, instruction in enumerate(colored_instructions, 1):
                        f.write(f"{i:4d}. {instruction}\n")
            else:
                pull_order_str = '-'.join([str(idx) for idx in pull_orders_r[:100]])
                
                # Save rectangle instructions to text file
                with open(instructions_path, 'w', encoding='utf-8') as f:
                    f.write(f"String Art Instructions\n")
                    f.write(f"======================\n\n")
                    f.write(f"Parameters:\n")
                    f.write(f"- Total Nails: {params['total_nails']}\n")
                    f.write(f"- Shape: {params.get('shape_type', 'circle')}\n")
                    f.write(f"- Output Size: {params['side_len']}px\n")
                    f.write(f"- String Strength: {params['export_strength']}\n")
                    f.write(f"- Max Iterations: {params.get('pull_amount', 'unlimited')}\n")
                    f.write(f"- Random Nails: {params.get('random_nails', 'all')}\n")
                    f.write(f"- White Background: {params.get('white_background', False)}\n\n")
                    f.write(f"Pull Order ({len(pull_orders_r)} total):\n")
                    f.write(f"{'='*30}\n")
                    for i, nail_idx in enumerate(pull_orders_r, 1):
                        f.write(f"{i:4d}. Nail {nail_idx}\n")
        
        else:
            update_progress(10, "Processing black and white...")
            # Black and white mode
            orig_pic = rgb2gray(img) * 0.9
            
            image_dimens = params['side_len'], params['side_len']
            
            if params.get('white_background'):
                str_pic = init_canvas(shape, black=False)  # Start with white canvas
                pull_order = create_art(nails, orig_pic, str_pic, -0.05, 
                                      i_limit=params.get('pull_amount'), 
                                      random_nails=params.get('random_nails'),
                                      progress_callback=lambda p, m: update_progress(10 + p*0.8, m))
                blank = init_canvas(image_dimens, black=False)  # White background
            else:
                str_pic = init_canvas(shape, black=True)   # Start with black canvas
                pull_order = create_art(nails, orig_pic, str_pic, 0.05, 
                                      i_limit=params.get('pull_amount'), 
                                      random_nails=params.get('random_nails'),
                                      progress_callback=lambda p, m: update_progress(10 + p*0.8, m))
                blank = init_canvas(image_dimens, black=True)   # Black background
            
            scaled_nails = scale_nails(
                image_dimens[1] / shape[1],
                image_dimens[0] / shape[0],
                nails
            )
            
            result = pull_order_to_array_bw(
                pull_order,
                blank,
                scaled_nails,
                -abs(params['export_strength']) if params.get('white_background') else abs(params['export_strength'])
            )
            
            # Generate colored instructions for circle mode
            if params.get('shape_type') == 'circle':
                colored_instructions = convert_pull_order_to_colored(pull_order, params['total_nails'])
                pull_order_str = ' | '.join(colored_instructions[:20])  # Show first 20 instructions
                
                # Save full instructions to text file
                with open(instructions_path, 'w', encoding='utf-8') as f:
                    f.write(f"String Art Instructions\n")
                    f.write(f"======================\n\n")
                    f.write(f"Parameters:\n")
                    f.write(f"- Total Nails: {params['total_nails']}\n")
                    f.write(f"- Shape: {params.get('shape_type', 'circle')}\n")
                    f.write(f"- Output Size: {params['side_len']}px\n")
                    f.write(f"- String Strength: {params['export_strength']}\n")
                    f.write(f"- Max Iterations: {params.get('pull_amount', 'unlimited')}\n")
                    f.write(f"- Random Nails: {params.get('random_nails', 'all')}\n")
                    f.write(f"- White Background: {params.get('white_background', False)}\n\n")
                    f.write(f"Quadrant Layout:\n")
                    f.write(f"- Blue: 12 o'clock (indices 150-199)\n")
                    f.write(f"- Red: 3 o'clock (indices 0-49)\n")
                    f.write(f"- Green: 6 o'clock (indices 50-99)\n")
                    f.write(f"- Yellow: 9 o'clock (indices 100-149)\n\n")
                    f.write(f"Instructions ({len(colored_instructions)} total):\n")
                    f.write(f"{'='*50}\n")
                    for i, instruction in enumerate(colored_instructions, 1):
                        f.write(f"{i:4d}. {instruction}\n")
            else:
                pull_order_str = '-'.join([str(idx) for idx in pull_order[:100]])
                
                # Save rectangle instructions to text file
                with open(instructions_path, 'w', encoding='utf-8') as f:
                    f.write(f"String Art Instructions\n")
                    f.write(f"======================\n\n")
                    f.write(f"Parameters:\n")
                    f.write(f"- Total Nails: {params['total_nails']}\n")
                    f.write(f"- Shape: {params.get('shape_type', 'circle')}\n")
                    f.write(f"- Output Size: {params['side_len']}px\n")
                    f.write(f"- String Strength: {params['export_strength']}\n")
                    f.write(f"- Max Iterations: {params.get('pull_amount', 'unlimited')}\n")
                    f.write(f"- Random Nails: {params.get('random_nails', 'all')}\n")
                    f.write(f"- White Background: {params.get('white_background', False)}\n\n")
                    f.write(f"Pull Order ({len(pull_order)} total):\n")
                    f.write(f"{'='*30}\n")
                    for i, nail_idx in enumerate(pull_order, 1):
                        f.write(f"{i:4d}. Nail {nail_idx}\n")
        
        update_progress(95, "Saving result...")
        
        # Save result
        mpimg.imsave(output_path, result, cmap=plt.get_cmap("gray"), vmin=0.0, vmax=1.0)
        
        # Mark as completed
        progress_data[task_id] = {
            'progress': 100,
            'message': 'Completed!',
            'status': 'completed',
            'result': {
                'success': True,
                'output_file': output_filename,
                'instructions_file': instructions_filename,
                'nails_count': len(nails),
                'pull_order': pull_order_str
            }
        }
        
    except Exception as e:
        progress_data[task_id] = {
            'progress': 0,
            'message': f'Error: {str(e)}',
            'status': 'error',
            'result': {
                'success': False,
                'error': str(e)
            }
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def api_process():
    """API endpoint for processing string art"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)
    
    # Get parameters
    params = {
        'total_nails': int(request.form.get('total_nails', 200)),
        'side_len': int(request.form.get('side_len', 800)),
        'export_strength': float(request.form.get('export_strength', 0.1)),
        'pull_amount': int(request.form.get('pull_amount', 2000)) if request.form.get('pull_amount') else None,
        'random_nails': int(request.form.get('random_nails')) if request.form.get('random_nails') else None,
        'white_background': request.form.get('white_background') == 'true',
        'rgb_mode': request.form.get('rgb_mode') == 'true',
        'shape_type': request.form.get('shape_type', 'circle')
    }
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Start async processing
    thread = threading.Thread(target=process_string_art_async, args=(filepath, params, task_id))
    thread.daemon = True
    thread.start()
    
    # Clean up uploaded file after a delay
    def cleanup_file():
        time.sleep(1)  # Give thread time to read the file
        try:
            os.remove(filepath)
        except:
            pass
    
    cleanup_thread = threading.Thread(target=cleanup_file)
    cleanup_thread.daemon = True
    cleanup_thread.start()
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': 'Processing started'
    })

@app.route('/api/download/<filename>')
def download_file(filename):
    """Download processed image"""
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/view/<filename>')
def view_file(filename):
    """View processed image"""
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath)
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    """Get progress for a specific task"""
    if task_id in progress_data:
        return jsonify(progress_data[task_id])
    else:
        return jsonify({'error': 'Task not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=os.getenv("PORT", default=5001)) 