from albumentations.pytorch import ToTensorV2
from django.urls import reverse
from matplotlib import pyplot as plt
import albumentations as A
import torch.nn as nn
from medpy.io import load
import os
import numpy as np
import torch
from django.shortcuts import redirect, render
from Models_app.forms import UploadForm
import cv2
import uuid
import threading
from django.http import JsonResponse, HttpResponse, HttpRequest
import json
from django.views.decorators.csrf import csrf_exempt
from matplotlib.path import Path
import shutil

model_lock = threading.Lock()
global_model = None


def conv_plus_conv(in_channels: int, out_channels: int):
    return nn.Sequential(
        nn.Conv2d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False
        ),
        nn.BatchNorm2d(num_features=out_channels),
        nn.ReLU(),
        nn.Conv2d(
            in_channels=out_channels,
            out_channels=out_channels,
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False
        ),
        nn.BatchNorm2d(num_features=out_channels),
        nn.ReLU(),
    )


class UNET(nn.Module):
    def __init__(self):
        super().__init__()

        base_channels = 8

        self.down1 = conv_plus_conv(1, base_channels)
        self.down2 = conv_plus_conv(base_channels, base_channels * 2)
        self.down3 = conv_plus_conv(base_channels * 2, base_channels * 4)
        self.down4 = conv_plus_conv(base_channels * 4, base_channels * 8)
        self.down5 = conv_plus_conv(base_channels * 8, base_channels * 16)

        self.up1 = conv_plus_conv(base_channels * 2, base_channels)
        self.up2 = conv_plus_conv(base_channels * 4, base_channels)
        self.up3 = conv_plus_conv(base_channels * 8, base_channels * 2)
        self.up4 = conv_plus_conv(base_channels * 16, base_channels * 4)
        self.up5 = conv_plus_conv(base_channels * 32, base_channels * 8)

        self.out = nn.Conv2d(in_channels=base_channels, out_channels=1, kernel_size=1)

        self.downsample = nn.MaxPool2d(kernel_size=2)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        residual1 = self.down1(x)
        x = self.downsample(residual1)

        residual2 = self.down2(x)
        x = self.downsample(residual2)

        residual3 = self.down3(x)
        x = self.downsample(residual3)

        residual4 = self.down4(x)
        x = self.downsample(residual4)

        residual5 = self.down5(x)
        x = self.downsample(residual5)

        x = nn.functional.interpolate(x, scale_factor=2)
        x = torch.cat((x, residual5), dim=1)
        x = self.up5(x)

        x = nn.functional.interpolate(x, scale_factor=2)
        x = torch.cat((x, residual4), dim=1)
        x = self.up4(x)

        x = nn.functional.interpolate(x, scale_factor=2)
        x = torch.cat((x, residual3), dim=1)
        x = self.up3(x)

        x = nn.functional.interpolate(x, scale_factor=2)
        x = torch.cat((x, residual2), dim=1)
        x = self.up2(x)

        x = nn.functional.interpolate(x, scale_factor=2)
        x = torch.cat((x, residual1), dim=1)
        x = self.up1(x)

        return self.sigmoid(self.out(x))


def load_global_model():
    global global_model
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    global_model = UNET()
    checkpoint = torch.load('staticfiles/model/liver_512_089.pth', map_location=device)
    global_model.load_state_dict(checkpoint)
    global_model.to(device)
    global_model.eval()


load_global_model()


def get_user_uuid(request):
    if 'user_uuid' not in request.session:
        request.session['user_uuid'] = str(uuid.uuid4())
    return request.session['user_uuid']


class Model:
    def __init__(self, device, image_path, output_dir):
        self.device = device
        self.orig_path = image_path
        self.output_dir = output_dir
        self.model = global_model
        self.data = self.load_data()
        self.flag = self.prepare()

    def prepare(self):
        self.show_result(self.data)
        return True

    def load_data(self):
        mean, std = (-485.18832664531345, 492.3121911082333)
        trans = A.Compose([A.Resize(height=512, width=512), ToTensorV2()])
        img = load(self.orig_path)[0]
        img[img > 1192] = 1192
        ans = trans(image=((img - mean) / std))
        return ans['image']

    def show_result(self, image):
        with model_lock:
            pred = (self.model(image.to(self.device).float().unsqueeze(0)).squeeze(0).cpu().detach() > 0.9)
        original_path = os.path.join(self.output_dir, 'original.png')
        plt.imsave(original_path, image.squeeze(), cmap='gray')
        fig = plt.figure(frameon=False)
        fig.set_size_inches(1, 1)
        ax = plt.Axes(fig, [0., 0., 1., 1.])
        ax.set_axis_off()
        fig.add_axes(ax)
        image = image.squeeze()
        pred_8uc1 = (pred.numpy().squeeze() * 255).astype(np.uint8)
        contours_pred, _ = cv2.findContours(pred_8uc1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        ax.imshow(image.squeeze(), cmap='gray')
        ax.imshow(pred.squeeze(), alpha=0.5, cmap='gray')
        for contour in contours_pred:
            ax.plot(contour[:, 0, 0], contour[:, 0, 1], 'r', linewidth=1)

        prediction_path = os.path.join(self.output_dir, 'prediction.png')
        fig.savefig(prediction_path, dpi=512)

        np.save(os.path.join(self.output_dir, 'original.npy'), image.squeeze())


def main_page(request):
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            dcm_file = form.cleaned_data['dcm_file']
            if dcm_file:
                user_uuid = get_user_uuid(request)
                input_dir = f'staticfiles/input/{user_uuid}/'
                os.makedirs(input_dir, exist_ok=True)
                file_path = os.path.join(input_dir, f'{uuid.uuid4()}.dcm')
                with open(file_path, 'wb') as f:
                    for chunk in dcm_file.chunks():
                        f.write(chunk)
                request.session['uploaded_file_path_dcm'] = file_path
                mean, std = (-485.18832664531345, 492.3121911082333)
                trans = A.Compose([A.Resize(height=512, width=512), ToTensorV2()])
                img = load(file_path)[0]
                ans = trans(image=((img - mean) / std))
                img_3d = ans['image']
                output_image_path = os.path.join(input_dir, f'uploaded_image.png')
                plt.imsave(output_image_path, img_3d[0], cmap='gray')
                request.session['uploaded_file_path_png'] = output_image_path
                return redirect('predict')
        else:
            return render(request, 'mainpage.html', {'form': form})
    else:
        form = UploadForm()
    return render(request, 'mainpage.html', {'form': form})


def watching_photos(request):
    file_path = request.session.get('uploaded_file_path_png')
    if not file_path or not os.path.exists(file_path):
        return redirect('main')
    return render(request, 'watching.html', context={'image_path': file_path[12:]})


def predict(request):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    user_uuid = get_user_uuid(request)
    output_dir = f'staticfiles/output/{user_uuid}/'
    os.makedirs(output_dir, exist_ok=True)

    file_path = request.session.get('uploaded_file_path_dcm')
    if not file_path or not os.path.exists(file_path):
        return redirect('main')

    Model(device=device, image_path=file_path, output_dir=output_dir)
    request.session['output_dir'] = output_dir
    return redirect('results')


def results(request):
    user_uuid = get_user_uuid(request)
    output_dir = request.session.get('output_dir', '')
    if not output_dir or not os.path.exists(output_dir):
        return redirect('main')

    output_pred_path = os.path.join(output_dir, 'prediction.png')
    output_image_path = os.path.join(output_dir, 'original.png')
    return render(request, 'result.html',
                  context={'output_pred': output_pred_path[12:],
                           'output_orig': output_image_path[12:]})


def clear_input(request):
    user_uuid = get_user_uuid(request)
    input_dir = f'staticfiles/input/{user_uuid}/'
    if os.path.exists(input_dir):
        for file_name in os.listdir(input_dir):
            file_path = os.path.join(input_dir, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
    return redirect('clear_output')


def clear_output(request):
    user_uuid = get_user_uuid(request)
    output_dir = f'staticfiles/output/{user_uuid}/'
    if os.path.exists(output_dir):
        for file_name in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
    return redirect('main')


def annotation(request):
    output_dir = f'staticfiles/output/{get_user_uuid(request)}/'
    step = get_step_dir(output_dir)
    if os.path.exists(os.path.join(output_dir, step, 'original.png')):
        original_path = os.path.join(output_dir, step, 'original.png')
    else:
        original_path = os.path.join(output_dir, 'original.png')

    data = {'img': original_path[11:]}
    return render(request, 'annotation.html', data)


def get_step_dir(dir, plus: int = 0) -> str:
    folders = [int(i.split('/')[-1]) for i in os.listdir(dir) if os.path.isdir(os.path.join(dir, i))]
    if folders:
        return str(max(folders) + plus)
    return '1'


def generate_mask(points, dir_save):
    mask = np.zeros((512, 512), dtype=np.uint8)

    step = get_step_dir(dir_save, 1)
    step_back = get_step_dir(dir_save)
    dir_client_np = os.path.join(dir_save, step_back, 'client.npy')

    if len(points) > 2:
        os.mkdir(os.path.join(dir_save, step))
        path = Path([(point["x"], point["y"]) for point in points])
        y_indices, x_indices = np.meshgrid(np.arange(mask.shape[0]), np.arange(mask.shape[1]))
        points_array = np.column_stack((x_indices.ravel(), y_indices.ravel()))
        mask[path.contains_points(points_array).reshape(mask.shape)] = 255

        rotated_image = np.rot90(mask, k=3)

        flipped_image = np.fliplr(rotated_image)

        fig = plt.figure(frameon=False)
        fig.set_size_inches(1, 1)
        ax = plt.Axes(fig, [0., 0., 1., 1.])
        ax.set_axis_off()
        fig.add_axes(ax)

        if os.path.exists(dir_client_np):
            flipped_image = np.logical_or(np.load(dir_client_np), flipped_image)

        ax.imshow(np.load(os.path.join(dir_save, 'original.npy')), cmap='gray')
        ax.imshow(flipped_image, alpha=0.5, cmap='gray')

        # SAVE ALL
        fig.savefig(os.path.join(dir_save, step, 'original.png'), dpi=512)
        plt.imsave(os.path.join(dir_save, step, 'client.png'), flipped_image, cmap="gray")
        np.save(os.path.join(dir_save, step, 'client.npy'), flipped_image)


@csrf_exempt
def save_mask(request):
    output_dir = f'staticfiles/output/{get_user_uuid(request)}/'
    if request.method == "POST":
        data = json.loads(request.body)
        points = data.get('points', [])
        generate_mask(points, output_dir)

    return JsonResponse({'redirect_url': reverse('download_file'), 'redirect_main': reverse('main')})


# TODO: Добавить возможность отправлять данные на дообучение
def download_file(request):
    output_dir = f'staticfiles/output/{get_user_uuid(request)}/'
    step = get_step_dir(output_dir)

    if os.path.exists(os.path.join(output_dir, step, 'client.png')):
        save_dir = os.path.join(output_dir, step, 'client.png')
    else:
        save_dir = os.path.join(output_dir, 'original.png')

    with open(save_dir, 'rb') as f:
        file_data = f.read()

    response = HttpResponse(file_data, content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="client_mask.png"'

    shutil.rmtree(output_dir)

    return response


@csrf_exempt
def add_mask(request):
    output_dir = f'staticfiles/output/{get_user_uuid(request)}/'

    if request.method == "POST":
        data = json.loads(request.body)
        points = data.get('points', [])
        generate_mask(points, output_dir)

    return HttpResponse()


@csrf_exempt
def del_mask(request):
    output_dir = f'staticfiles/output/{get_user_uuid(request)}/'
    step = get_step_dir(output_dir, 1)
    new_dir = os.path.join(output_dir, step, 'restored_image.png')
    os.makedirs(os.path.dirname(new_dir), exist_ok=True)
    original_dir_np = os.path.join(output_dir, 'original.npy')

    plt.imsave(new_dir, np.load(original_dir_np), cmap="gray")

    return HttpResponse()
