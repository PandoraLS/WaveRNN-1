import glob
from utils.display import *
from utils.dsp import *
from utils import hparams as hp
from multiprocessing import Pool, cpu_count
from utils.paths import Paths
import pickle
import argparse
from utils.text.recipes import ljspeech
from utils.files import get_files
from pathlib import Path


"""
对音频文件预处理，将wav文件处理为mel谱或对其量化并保存到文件
usage:
    python preprocess.py --path /Users/lisen/workspace/datasets/LJSpeech-1.1
Note: 注意设置hparams.py中wav_path和data_path的位置，如果不设置，那么会在代码跟目录新建一个文件夹 data/ ，生成的mel文件都会放到data/文件夹中,本地调试最好生成到其他地方
"""

# Helper functions for argument types
def valid_n_workers(num):
    n = int(num)
    if n < 1:
        raise argparse.ArgumentTypeError('%r must be an integer greater than 0' % num)
    return n

parser = argparse.ArgumentParser(description='Preprocessing for WaveRNN and Tacotron')
parser.add_argument('--path', '-p', help='directly point to dataset path (overrides hparams.wav_path')
parser.add_argument('--extension', '-e', metavar='EXT', default='.wav', help='file extension to search for in dataset folder')
parser.add_argument('--num_workers', '-w', metavar='N', type=valid_n_workers, default=cpu_count()-1, help='The number of worker threads to use for preprocessing')
parser.add_argument('--hp_file', metavar='FILE', default='hparams.py', help='The file to use for the hyperparameters')
args = parser.parse_args()

hp.configure(args.hp_file)  # Load hparams from file
if args.path is None:
    args.path = hp.wav_path # LJSpeech-1.1/ 文件夹路径

extension = args.extension
path = args.path

def convert_file(path: Path):
    """
    将wav文件转换为mel(mel谱) 和 quant(量化)
    Args:
        path: wav文件路径
    Returns: wav文件的梅尔谱 和 量化结果
    """
    y = load_wav(path)
    peak = np.abs(y).max()
    if hp.peak_norm or peak > 1.0:
        y /= peak
    mel = melspectrogram(y)
    if hp.voc_mode == 'RAW': # raw mu-律
        quant = encode_mu_law(y, mu=2**hp.bits) if hp.mu_law else float_2_label(y, bits=hp.bits)
    elif hp.voc_mode == 'MOL': # 常规的量化, 不进行mu-律变换 bits=16
        quant = float_2_label(y, bits=16)
    return mel.astype(np.float32), quant.astype(np.int64)


def process_wav(path: Path):
    """
    处理wav文件，并将mel谱 和 量化后的值保存下来
    Args:
        path: wav文件路径
    Returns: wav文件id 和 mel谱
    """
    wav_id = path.stem # 最后一个路径组件去除后缀 比如: LJ001.wav -> LJ001
    m, x = convert_file(path)
    np.save(paths.mel/f'{wav_id}.npy', m, allow_pickle=False)
    np.save(paths.quant/f'{wav_id}.npy', x, allow_pickle=False)
    return wav_id, m.shape[-1]

wav_files = get_files(path, extension) # 获取path路径下所有.wav文件
paths = Paths(hp.data_path, hp.voc_model_id, hp.tts_model_id)

print(f'\n{len(wav_files)} {extension[1:]} files found in "{path}"\n')

if len(wav_files) == 0:

    print('Please point wav_path in hparams.py to your dataset,')
    print('or use the --path option.\n')

else:

    if not hp.ignore_tts:

        text_dict = ljspeech(path)

        with open(paths.data/'text_dict.pkl', 'wb') as f:
            pickle.dump(text_dict, f)

    n_workers = max(1, args.num_workers)

    simple_table([
        ('Sample Rate', hp.sample_rate),
        ('Bit Depth', hp.bits),
        ('Mu Law', hp.mu_law),
        ('Hop Length', hp.hop_length),
        ('CPU Usage', f'{n_workers}/{cpu_count()}')
    ])

    pool = Pool(processes=n_workers)
    dataset = []

    for i, (item_id, length) in enumerate(pool.imap_unordered(process_wav, wav_files), 1):
        dataset += [(item_id, length)]
        bar = progbar(i, len(wav_files))
        message = f'{bar} {i}/{len(wav_files)} '
        stream(message)

    with open(paths.data/'dataset.pkl', 'wb') as f:
        pickle.dump(dataset, f)

    print('\n\nCompleted. Ready to run "python train_tacotron.py" or "python train_wavernn.py". \n')
