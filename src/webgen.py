import os
import sys
import shutil
import urllib.request
import zipfile
import gdown
from argparse import ArgumentParser

import gradio as gr
from main import song_cover_pipeline

# Define directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RVC_MODELS_DIR = os.path.join(BASE_DIR, 'rvc_models')
OUTPUT_DIR = os.path.join(BASE_DIR, 'song_output')

# ----------------------------
# Helper Functions for Models
# ----------------------------
def get_current_models(models_dir: str) -> list:
    items_to_remove = ['hubert_base.pt', 'MODELS.txt', 'rmvpe.pt', 'fcpe.pt']
    return [item for item in os.listdir(models_dir) if item not in items_to_remove]

def update_models_list() -> gr.update:
    models_list = get_current_models(RVC_MODELS_DIR)
    return gr.update(choices=models_list)

def extract_zip(extraction_folder: str, zip_name: str):
    os.makedirs(extraction_folder, exist_ok=True)
    with zipfile.ZipFile(zip_name, 'r') as zip_ref:
        zip_ref.extractall(extraction_folder)
    os.remove(zip_name)
    index_filepath, model_filepath = None, None
    for root, _, files in os.walk(extraction_folder):
        for name in files:
            full_path = os.path.join(root, name)
            if name.endswith('.index') and os.stat(full_path).st_size > 1024 * 100:
                index_filepath = full_path
            if name.endswith('.pth') and os.stat(full_path).st_size > 1024 * 1024 * 40:
                model_filepath = full_path
    if not model_filepath:
        raise gr.Error(f'No .pth model file found in {extraction_folder}. Please check the zip contents.')
    os.rename(model_filepath, os.path.join(extraction_folder, os.path.basename(model_filepath)))
    if index_filepath:
        os.rename(index_filepath, os.path.join(extraction_folder, os.path.basename(index_filepath)))
    for item in os.listdir(extraction_folder):
        item_path = os.path.join(extraction_folder, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)

def download_online_model(url: str, dir_name: str, progress=gr.Progress()):
    try:
        progress(0, desc=f'[~] Downloading voice model: {dir_name}...')
        zip_name = url.split('/')[-1]
        extraction_folder = os.path.join(RVC_MODELS_DIR, dir_name)
        if os.path.exists(extraction_folder):
            raise gr.Error(f'Model directory {dir_name} already exists! Please choose a different name.')
        if 'huggingface.co' in url:
            urllib.request.urlretrieve(url, zip_name)
        elif 'pixeldrain.com' in url:
            zip_name = f'{dir_name}.zip'
            url = f'https://pixeldrain.com/api/file/{zip_name}'
            urllib.request.urlretrieve(url, zip_name)
        elif 'drive.google.com' in url:
            zip_name = f'{dir_name}.zip'
            file_id = url.split('/')[-2]
            output = os.path.join('.', zip_name)
            gdown.download(id=file_id, output=output, quiet=False)
        progress(0.5, desc='[~] Extracting model zip...')
        extract_zip(extraction_folder, zip_name)
        print(f'[+] Model {dir_name} successfully downloaded!')
        return f'[+] Model {dir_name} successfully downloaded!'
    except Exception as e:
        raise gr.Error(str(e))

def upload_local_model(zip_path, dir_name: str, progress=gr.Progress()):
    try:
        extraction_folder = os.path.join(RVC_MODELS_DIR, dir_name)
        if os.path.exists(extraction_folder):
            raise gr.Error(f'Model directory {dir_name} already exists! Please choose a different name.')
        zip_name = zip_path.name
        progress(0.5, desc='[~] Extracting uploaded model zip...')
        extract_zip(extraction_folder, zip_name)
        return f'[+] Model {dir_name} successfully uploaded!'
    except Exception as e:
        raise gr.Error(str(e))

# ----------------------------
# Helper Functions for UI
# ----------------------------
def swap_visibility():
    return gr.update(visible=True), gr.update(visible=False), gr.update(value=''), gr.update(value=None)

def process_file_upload(file):
    return file.name, gr.update(value=file.name)

def show_hop_slider(pitch_detection_algo: str):
    if pitch_detection_algo in [
        'rmvpe+', 'mangio-crepe', 'hybrid[rmvpe+mangio-crepe]',
        'hybrid[mangio-crepe+rmvpe]', 'hybrid[mangio-crepe+fcpe]',
        'hybrid[mangio-crepe+rmvpe+fcpe]'
    ]:
        return gr.update(visible=True)
    else:
        return gr.update(visible=False)

def show_pitch_slider(pitch_detection_algo: str):
    if pitch_detection_algo == 'rmvpe+':
        return gr.update(visible=True), gr.update(visible=True)
    else:
        return gr.update(visible=False), gr.update(visible=False)

def update_f0_method(use_hybrid_methods: bool):
    if use_hybrid_methods:
        return gr.update(choices=[
            'hybrid[rmvpe+fcpe]', 'hybrid[rmvpe+mangio-crepe]',
            'hybrid[mangio-crepe+rmvpe]', 'hybrid[mangio-crepe+fcpe]',
            'hybrid[mangio-crepe+rmvpe+fcpe]'
        ], value='hybrid[rmvpe+fcpe]')
    else:
        return gr.update(choices=['rmvpe+', 'fcpe', 'rmvpe', 'mangio-crepe'], value='rmvpe+')

def reset_defaults():
    return [
        0, 0.5, 3, 0.25, 0.33, 128, 0, 0, 0, 0.25, 0.75, 0.05, 0.85, 0.5, 0, 0,
        4, -16, -1, 3, -30, 6, 10, 100, 0, 0, 0, 0, 0, 50, 1100, None, None, None, None, None
    ]

# ----------------------------
# UI Component Builders
# ----------------------------
def create_download_models_tab():
    with gr.TabItem("Download Models"):
        with gr.Row():
            url_mod = gr.Text(label="Model URL", placeholder="Enter model URL...")
            mod_name = gr.Text(label="Model Name", placeholder="Enter model name...")
        download_btn = gr.Button("Download Model", variant='primary')
        download_btn.click(download_online_model, inputs=[url_mod, mod_name], outputs=None)

def create_covergen_tab():
    """Create the 'CoverGen' tab UI with an improved, responsive layout for desktop and mobile."""
    voice_models = get_current_models(RVC_MODELS_DIR)
    with gr.TabItem("CoverGen"):
        gr.Markdown(
            """
            # AI Cover Generator
            Transform a song into an AI-generated cover. Use the tabs below to switch between Input/Voice settings and Transformation/Effects.
            """
        )
        # Use sub-tabs to separate related settings
        with gr.Tabs():
            with gr.TabItem("Input & Voice"):
                gr.Markdown("### Input Source")
                song_input = gr.Text(
                    label='YouTube Link or Local File Path',
                    placeholder='Enter a YouTube URL or file path...'
                )
                upload_button = gr.UploadButton(
                    'Upload Audio', file_types=['audio'], variant='primary'
                )
                with gr.Row(visible=False) as file_upload_row:
                    local_file = gr.File(label='Uploaded Audio File')
                    switch_input_btn = gr.Button('Switch to Text Input')
                    switch_input_btn.click(
                        swap_visibility,
                        outputs=[song_input, file_upload_row, song_input, local_file]
                    )
                upload_button.upload(
                    process_file_upload,
                    inputs=[upload_button],
                    outputs=[local_file, song_input]
                )
                gr.Markdown("### Voice Settings")
                voice_model_dropdown = gr.Dropdown(
                    voice_models, label='Voice Models',
                    info='Models are located in "CoverGen/rvc_models". Click "Update Models List" after adding new models.'
                )
                update_btn = gr.Button('Update Models List 🔁', variant='primary')
                update_btn.click(update_models_list, None, outputs=voice_model_dropdown)
                pitch = gr.Slider(
                    -24, 24, value=0, step=1, label='Voice Pitch Shift',
                    info='Shift pitch: negative for a deeper tone, positive for a brighter tone'
                )
                f0autotune = gr.Checkbox(
                    label="Auto-tuning",
                    info='Automatically adjust pitch for more harmonious vocals',
                    value=False
                )
            with gr.TabItem("Transform & Effects"):
                with gr.Accordion('Voice Transformation Settings', open=True):
                    gr.Markdown("#### Basic Settings")
                    with gr.Row():
                        index_rate = gr.Slider(
                            0, 1, value=0.5, label='Indexing Speed',
                            info="Balance between voice character and artifact reduction"
                        )
                        filter_radius = gr.Slider(
                            0, 7, value=3, step=1, label='Filter Radius',
                            info='Median filtering to reduce noise'
                        )
                    with gr.Row():
                        rms_mix_rate = gr.Slider(
                            0, 1, value=0.25, label='RMS Mix Rate',
                            info="Preserves original volume characteristics"
                        )
                        protect = gr.Slider(
                            0, 0.5, value=0.33, label='Protection Level',
                            info='Protects plosives and breathing sounds'
                        )
                    gr.Markdown("#### Pitch Extraction Settings")
                    with gr.Row():
                        with gr.Column():
                            use_hybrid_methods = gr.Checkbox(
                                label="Use Hybrid Methods", value=False
                            )
                            f0_method = gr.Dropdown(
                                ['rmvpe+', 'fcpe', 'rmvpe', 'mangio-crepe'],
                                value='rmvpe+', label='Pitch Extraction Method'
                            )
                            use_hybrid_methods.change(
                                update_f0_method, inputs=use_hybrid_methods, outputs=f0_method
                            )
                        crepe_hop_length = gr.Slider(
                            8, 512, value=128, step=8, label='Hop Length',
                            info='Smaller values improve pitch accuracy at the cost of speed'
                        )
                        f0_method.change(
                            show_hop_slider, inputs=f0_method, outputs=crepe_hop_length
                        )
                    with gr.Row():
                        f0_min = gr.Slider(
                            1, 16000, value=50, step=1, label="Min Pitch (Hz)",
                            info="Lower bound for pitch detection"
                        )
                        f0_max = gr.Slider(
                            1, 16000, value=1100, step=1, label="Max Pitch (Hz)",
                            info="Upper bound for pitch detection"
                        )
                        f0_method.change(
                            show_pitch_slider, inputs=f0_method, outputs=[f0_min, f0_max]
                        )
                    keep_files = gr.Checkbox(
                        label='Save intermediate files',
                        info='Keep temporary audio files for debugging',
                        visible=False
                    )
                with gr.Accordion('Audio Mixing & Effects', open=False):
                    gr.Markdown("#### Volume Adjustment (dB)")
                    with gr.Row():
                        main_gain = gr.Slider(
                            -20, 20, value=0, step=1, label='Main Vocal'
                        )
                        backup_gain = gr.Slider(
                            -20, 20, value=0, step=1, label='Backup Vocal'
                        )
                        inst_gain = gr.Slider(
                            -20, 20, value=0, step=1, label='Music'
                        )
                    with gr.Accordion('Effects', open=False):
                        with gr.Accordion('Reverb', open=False):
                            with gr.Row():
                                reverb_rm_size = gr.Slider(
                                    0, 1, value=0.25, label='Room Size'
                                )
                                reverb_width = gr.Slider(
                                    0, 1, value=0.75, label='Reverb Width'
                                )
                            with gr.Row():
                                reverb_wet = gr.Slider(
                                    0, 1, value=0.05, label='Wet Level'
                                )
                                reverb_dry = gr.Slider(
                                    0, 1, value=0.85, label='Dry Level'
                                )
                                reverb_damping = gr.Slider(
                                    0, 1, value=0.5, label='Damping Level'
                                )
                        with gr.Accordion('Echo', open=False):
                            with gr.Row():
                                delay_time = gr.Slider(
                                    0, 2, value=0, label='Delay Time'
                                )
                                delay_feedback = gr.Slider(
                                    0, 1, value=0, label='Feedback Level'
                                )
                        with gr.Accordion('Chorus', open=False):
                            with gr.Row():
                                chorus_rate_hz = gr.Slider(
                                    0.1, 10, value=0, label='Chorus Rate (Hz)'
                                )
                                chorus_depth = gr.Slider(
                                    0, 1, value=0, label='Chorus Depth'
                                )
                            with gr.Row():
                                chorus_centre_delay_ms = gr.Slider(
                                    0, 50, value=0, label='Center Delay (ms)'
                                )
                                chorus_feedback = gr.Slider(
                                    0, 1, value=0, label='Feedback'
                                )
                                chorus_mix = gr.Slider(
                                    0, 1, value=0, label='Mix'
                                )
                    with gr.Accordion('Processing', open=False):
                        with gr.Accordion('Compressor', open=False):
                            with gr.Row():
                                compressor_ratio = gr.Slider(
                                    1, 20, value=4, label='Compressor Ratio'
                                )
                                compressor_threshold = gr.Slider(
                                    -60, 0, value=-16, label='Compressor Threshold'
                                )
                        with gr.Accordion('Limiter', open=False):
                            limiter_threshold = gr.Slider(
                                -12, 0, value=0, label='Limiter Threshold'
                            )
                        with gr.Accordion('Filters', open=False):
                            with gr.Row():
                                low_shelf_gain = gr.Slider(
                                    -20, 20, value=-1, label='Low Shelf Gain'
                                )
                                high_shelf_gain = gr.Slider(
                                    -20, 20, value=3, label='High Shelf Gain'
                                )
                        with gr.Accordion('Noise Reduction', open=False):
                            with gr.Row():
                                noise_gate_threshold = gr.Slider(
                                    -60, 0, value=-30, label='Noise Gate Threshold'
                                )
                                noise_gate_ratio = gr.Slider(
                                    1, 20, value=6, label='Noise Gate Ratio'
                                )
                            with gr.Row():
                                noise_gate_attack = gr.Slider(
                                    0, 100, value=10, label='Noise Gate Attack (ms)'
                                )
                                noise_gate_release = gr.Slider(
                                    0, 1000, value=100, label='Noise Gate Release (ms)'
                                )
                    with gr.Accordion('Other Effects', open=False):
                        with gr.Accordion('Distortion', open=False):
                            drive_db = gr.Slider(
                                -20, 20, value=0, label='Drive (dB)'
                            )
                        with gr.Accordion('Clipping', open=False):
                            clipping_threshold = gr.Slider(
                                -20, 0, value=0, label='Clipping Threshold'
                            )
        with gr.Row():
            with gr.Column(scale=2):
                generate_btn = gr.Button("Generate", variant='primary')
            with gr.Column(scale=5):
                ai_cover = gr.Audio(label='AI Cover', show_share_button=False)
                with gr.Accordion("Intermediate Audio Files", open=False):
                    ai_vocals = gr.Audio(label='Transformed Vocals', show_share_button=False)
                    main_vocals_dereverb = gr.Audio(label='Vocals', show_share_button=False)
                    backup_vocals = gr.Audio(label='Backup Vocals', show_share_button=False)
                    instrumentals = gr.Audio(label='Instrumental', show_share_button=False)
            with gr.Column(scale=1):
                output_format = gr.Dropdown(
                    ['mp3', 'flac', 'wav'], value='mp3', label='Output File Type'
                )
                clear_btn = gr.Button("Reset All Parameters", min_width=100)
        generate_btn.click(
            song_cover_pipeline,
            inputs=[
                song_input, voice_model_dropdown, pitch, keep_files, gr.Number(1, visible=False),
                main_gain, backup_gain, inst_gain, index_rate, filter_radius, rms_mix_rate,
                f0_method, crepe_hop_length, protect, reverb_rm_size, reverb_wet,
                reverb_dry, reverb_damping, reverb_width, low_shelf_gain, high_shelf_gain,
                limiter_threshold, compressor_ratio, compressor_threshold, delay_time,
                delay_feedback, noise_gate_threshold, noise_gate_ratio, noise_gate_attack,
                noise_gate_release, output_format, drive_db, chorus_rate_hz, chorus_depth,
                chorus_centre_delay_ms, chorus_feedback, chorus_mix, clipping_threshold,
                f0autotune, f0_min, f0_max
            ],
            outputs=[ai_cover, ai_vocals, main_vocals_dereverb, backup_vocals, instrumentals]
        )
        clear_btn.click(
            lambda: reset_defaults(),
            outputs=[
                pitch, index_rate, filter_radius, rms_mix_rate, protect, crepe_hop_length,
                main_gain, backup_gain, inst_gain, reverb_rm_size, reverb_width,
                reverb_wet, reverb_dry, reverb_damping, delay_time, delay_feedback,
                compressor_ratio, compressor_threshold, low_shelf_gain, high_shelf_gain,
                limiter_threshold, noise_gate_threshold, noise_gate_ratio, noise_gate_attack,
                noise_gate_release, drive_db, chorus_rate_hz, chorus_depth,
                chorus_centre_delay_ms, chorus_feedback, chorus_mix, clipping_threshold,
                f0autotune, f0_min, f0_max, ai_cover, ai_vocals, main_vocals_dereverb,
                backup_vocals, instrumentals
            ]
        )

def build_interface():
    # Custom CSS to ensure rows stack on narrow screens (mobile responsiveness)
    custom_css = """
    @media (max-width: 768px) {
        .gradio-container .row { 
            flex-direction: column !important; 
        }
    }
    """
    with gr.Blocks(
        title="CoverGen-RVC", 
        theme=gr.themes.Soft(primary_hue=gr.themes.colors.red, secondary_hue=gr.themes.colors.pink),
        css=custom_css
    ) as app:
        gr.Label("CoveR Gen RVC")
        with gr.Tabs():
            create_covergen_tab()
            create_download_models_tab()
    return app

if __name__ == '__main__':
    parser = ArgumentParser(
        description='Generate an AI cover of a song and output to song_output/id.',
        add_help=True
    )
    parser.add_argument("-s", "--share", action="store_true", dest="share_enabled", default=False, help="Allow sharing")
    parser.add_argument("-l", "--listen", action="store_true", default=False, help="Make the WebUI accessible on your local network.")
    parser.add_argument("-lh", '--listen-host', type=str, help='Hostname for the server.')
    parser.add_argument("-lp",  '--listen-port', type=int, help='Port for the server.')
    args = parser.parse_args()

    app = build_interface()
    app.launch(
        share=args.share_enabled,
        server_name=None if not args.listen else (args.listen_host or '0.0.0.0'),
        server_port=args.listen_port,
    )
