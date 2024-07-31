import os
import re
from flask import Flask, request, jsonify, send_file
import cv2
from pytubefix import YouTube
from fpdf import FPDF
from PIL import Image
import shutil

app = Flask(__name__)


def sanitize_filename(file_name):
    return re.sub(r'[<>:"/\\|?*]', '_', file_name)


def extract_frames(video_path, output_folder, minutes):
    video_capture = cv2.VideoCapture(video_path)
    frame_rate = int(video_capture.get(cv2.CAP_PROP_FPS))
    print("frame rate:", frame_rate)

    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    print("total frame:", total_frames)

    # Calculate frame interval based on minutes and frame rate
    frame_interval = int((frame_rate * 60) * int(minutes))
    print("minutes", minutes)
    print("frame interval:", (frame_interval))

    # Make sure frame_interval is not zero to avoid division by zero
    if frame_interval == 0:
        frame_interval = 1

    for i in range(0, total_frames, frame_interval):
        video_capture.set(cv2.CAP_PROP_POS_FRAMES, i)
        success, image = video_capture.read()

        if success:
            frame_path = os.path.join(output_folder, f'frame_{i}.jpg')
            cv2.imwrite(frame_path, image)

    video_capture.release()


def create_pdf_from_frames(output_folder):
    pdf = FPDF(format='A4')  # Adjust format as needed

    for root, _, files in os.walk(output_folder):
        image_files = [file for file in files if file.endswith('.jpg')]
        image_files.sort()

        for image_file in image_files:
            image_path = os.path.join(root, image_file)

            with Image.open(image_path) as img:
                img_width, img_height = img.size

            # Calculate scaled dimensions to fit within PDF page
            pdf_width, pdf_height = pdf.w, pdf.h
            scale = min(pdf_width / img_width, pdf_height / img_height)
            new_width = img_width * scale
            new_height = img_height * scale

            # Calculate center coordinates
            center_x = (pdf_width - new_width) / 2
            center_y = (pdf_height - new_height) / 2

            pdf.add_page()
            pdf.image(image_path, x=center_x, y=center_y, w=new_width, h=new_height)

    pdf_file_name = f'{output_folder}_frames.pdf'
    pdf.output(pdf_file_name)
    return pdf_file_name


@app.route('/convert_video_to_pdf', methods=['GET'])
def convert_video_to_pdf():
    youtube_url = request.args.get('youtube_url')
    minutes = request.args.get("time")

    try:
        yt = YouTube(youtube_url)
        sanitized_video_id = sanitize_filename(yt.video_id)
        video_folder = f'video_{sanitized_video_id}'
        os.makedirs(video_folder, exist_ok=True)

        video = yt.streams.filter(file_extension='mp4').first()
        if video:
            video_extension = video.mime_type.split('/')[-1]
            video_file_name = f'video.{video_extension}'
            video.download(output_path=video_folder, filename=video_file_name)
        else:
            return jsonify({'message': 'No downloadable video found'})

        extract_frames(os.path.join(video_folder, video_file_name), video_folder, minutes)

        pdf_file = create_pdf_from_frames(video_folder)
        shutil.rmtree(video_folder)
        return send_file(pdf_file, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)})


if __name__ == '__main__':
    app.run(debug=True)
