#!/usr/bin/env python3

import re
import sys
import time
import shutil
import argparse
from glob import glob
from tqdm import tqdm
from patterns import *
from scanner import scan
from random import randint
from subprocess import run, DEVNULL
from os import mkdir, remove, listdir, sep
from music21.meter import TimeSignature
from music21.key import Key, sharpsToPitch
from signal import signal, SIGINT, SIG_IGN
from multiprocessing import cpu_count, Pool
# from drum_note_processor import Note, NoteList
from os.path import join, dirname, exists, basename

def check(args):
    if not exists(args.input_dir):
        print("Input directory does not exist!")
        sys.exit(1)
    if exists(args.output_dir):
        if listdir(args.output_dir):
            print("The output contains data. Do you want to overwrite it?")
            result = input("[y]es/[n]o: ").lower()
            if not result in ["y", "yes"]:
                print("Aborted")
                sys.exit(0)
        shutil.rmtree(args.output_dir)
    mkdir(args.output_dir)

def __midi_to_csv(file_in, file_out):
    if args.verbose:
        process = run(["midicsv", file_in, file_out])
    else:
        process = run(["midicsv", file_in, file_out], stderr=DEVNULL)
    return process.returncode

def __csv_to_midi(file_in, file_out):
    if args.verbose:
        process = run(["csvmidi", file_in, file_out])
    else:
        process = run(["csvmidi", file_in, file_out], stderr=DEVNULL)
    return process.returncode

def midi_to_csv(file):
    folder = join(args.output_dir, file["name"])
    csv_file = join(folder, "{}_full.csv".format(file["name"]))
    mkdir(folder)
    code = __midi_to_csv(file["path"], csv_file)
    if code != 0:
        shutil.rmtree(folder)
        if args.verbose:
            return "Could not convert '{}'".format(file["name"])
    return None

def csv_to_midi(file):
    midi_file = join(dirname(file["path"]), "{}.mid".format(file["name"]))
    code = __csv_to_midi(file["path"], midi_file)
    if code != 0 and args.verbose:
        return "An error occurred while converting '{}' in folder {}".format(file["name"], dirname(file["path"]))
    return None

def transpose(file):
    data = []
    with open(file["path"], "r", encoding="latin-1") as f:
        for line in f:
            m= note_pattern.match(line)
            if m:
                if m.group(2) != drum_channel:
                    note = int(m.group(5)) + args.offset
                    if note < 0:
                        note = 0
                    data.append(re.sub(note_pattern, "\\1, \\2, \\3, \\4, {}, \\6".format(note), line))
                else:
                    data.append(line)
            else:
                data.append(line)
    with open(file["path"], "w", encoding="latin-1") as f:
        for line in data:
            f.write(line)

# def drums_to_bin(file):
#     file_in = file["path"]
#     root_folder = dirname(file["path"]).split("/")[-2]
#     # file_out = join(args.output_dir, "{}.txt".format(file["name"]))
#     file_out = join(dirname(file["path"]), "{}.txt".format(file["name"]))
#     data = open(file_in, "r", encoding="latin-1").readlines()
#     note_list = NoteList()
#     try:
#         with open(file_out, "w") as f:
#             for line in data:
#                 m = note_pattern.match(line)
#                 if m:
#                     pitch = int(m.group(5))
#                     tick = int(m.group(2))
#                     note = Note(pitch, tick)
#                     note_list.add_note(note)
#             note_list.quantise()
#             note_list.simplify_drums()
#             f.write(note_list.return_as_text())
#     except:
#         return "Could not convert file {}".format(file["name"])

def get_key(file):
    with open(file["path"], "r") as f:
        for line in f:
            m = key_signature_pattern.match(line)
            if m:
                return Key(sharpsToPitch(int(m.group(4))), m.group(5))

def get_time(file):
    with open(file["path"], "r") as f:
        for line in f:
            m = time_signature_pattern.match(line)
            if m:
                return TimeSignature("{}/{}".format(m.group(4), int(1 / 2**-int(m.group(5)))))

def get_tempo(file):
    with open(file["path"], "r") as f:
        for line in f:
            m = tempo_pattern.match(line)
            if m:
                return 60000000 // int(m.group(4))

def get_instrument(file):
    with open(file["path"], "r") as f:
        for line in f:
            m = program_change_pattern.match(line)
            if m:
                return int(m.group(5))

def get_channels(file):
    return [int(item["name"].split("_")[1]) for item in scan(dirname(file["path"]), "**/channel_*.csv", False)]

def filter_nonstandard(file):
    key = get_key(file)
    time = get_time(file)
    tempo = get_tempo(file)
    channels = get_channels(file)
    if not time or not key or key.mode not in ["major", "minor"] or time.ratioString != "4/4" or 9 not in channels:
        shutil.rmtree(dirname(file["path"]))

def move_to_output_folder(file):
    file_out = join(args.output_dir, "{}.mid".format(file["name"].replace("_full", "")))
    shutil.copyfile(file["path"], file_out)

def move_to_folder(file, folder):
    shutil.copyfile(file["path"], join(folder, file["name"]))

def filter_instruments(file):
    instrument = get_instrument(file)
    if not instrument and dirname(file["path"]).split(sep)[-1] != "channel_9":
        return
    if instrument in [*list(range(33, 41)), 44, 59, 68, 88]:
        file["name"] = "{}_{}.csv".format(dirname(file["path"]).split(sep)[-2], file["name"])
        move_to_folder(file, join(args.output_dir, "bass"))
    elif instrument in [*list(range(57, 65)), *list(range(0, 9)), 73, 74, *list(range(81, 88)), *list(range(89, 97))]:
        file["name"] = "{}_{}.csv".format(dirname(file["path"]).split(sep)[-2], file["name"])
        move_to_folder(file, join(args.output_dir, "melody"))
    elif dirname(file["path"]).split(sep)[-1] == "channel_9":
        file["name"] = "{}_{}.csv".format(dirname(file["path"]).split(sep)[-2], file["name"])
        move_to_folder(file, join(args.output_dir, "drums"))

def delete(file):
    remove(file["path"])

def main(args):
    with tqdm(total=(4 if args.offset != 0 else 3), unit="step") as bar:
        # tqdm.write("Analyzing songs...")
        # files = scan(args.input_dir, "**/*_full.csv", False)
        # with open(join(args.output_dir, "keys.csv"), "w") as out_file:
        #     out_file.write("Filename, Key Tonic, Key Mode, Key Combined, Time Signature, Tempo\n")
        #     for file in tqdm(files, total=len(files), unit="files"):
        #         key = get_key(file)
        #         time = get_time(file)
        #         tempo = get_tempo(file)
        #         out_file.write("{}, {}, {}, {}, {}, {}\n".format(file["name"], (key.tonic if key else "empty"), (key.mode if key else "empty"), (key if key else "empty"), (time.ratioString if time else "empty"), (tempo if tempo else 0)))
        # bar.update(1)

        mkdir(join(args.output_dir, "bass"))
        mkdir(join(args.output_dir, "melody"))
        mkdir(join(args.output_dir, "drums"))
        tqdm.write("Extracting 'trio' instruments (melody, bass, drums)...")
        files = scan(args.input_dir, "**/track_*.csv", True)
        for e in tqdm(worker_pool.imap_unordered(filter_instruments, files), total=len(files), unit="files"):
            if e:
                tqdm.write(e)
        bar.update(1)

        tqdm.write("Converting output data...")
        files = scan(args.output_dir, "melody/*.csv", False)
        files += scan(args.output_dir, "bass/*.csv", False)
        files += scan(args.output_dir, "drums/*.csv", False)
        for e in tqdm(worker_pool.imap_unordered(csv_to_midi, files), total=len(files), unit="files"):
            if e:
                tqdm.write(e)
        bar.update(1)

        tqdm.write("Removing temporary artifacts...")
        files = scan(args.output_dir, "**/*.csv", False)
        files += scan(args.output_dir, "**/*.txt", False)
        for e in tqdm(worker_pool.imap_unordered(delete, files), total=len(files), unit="files"):
            if e:
                tqdm.write(e)
        bar.update(1)

        print("")
        return

        # tqdm.write("Converting drum channel...")
        # files = scan(args.output_dir, "drums/*.csv", False)
        # for e in tqdm(worker_pool.imap_unordered(drums_to_bin, files), total=len(files), unit="files"):
        #     if e:
        #         tqdm.write(e)
        # bar.update(1)

        # tqdm.write("Merging tracks...")
        # files = scan(args.output_dir, "drums/*.txt", False)
        # with open(join(args.output_dir, "drums.txt"), "w") as out_file:
        #     for file in files:
        #         with open(file["path"], "r") as in_file:
        #             for line in in_file:
        #                 out_file.write(line)
        # bar.update(1)

        # tqdm.write("Filtering songs...")
        # files = scan(args.input_dir, "**/*_full.csv", False)
        # for e in tqdm(worker_pool.imap_unordered(filter_nonstandard, files), total=len(files), unit="files"):
        #     if e:
        #         tqdm.write(e)
        # bar.update(1)

        # tqdm.write("Converting output data...")
        # files = scan(args.input_dir, "**/*_full.csv", False)
        # for e in tqdm(worker_pool.imap_unordered(csv_to_midi, files), total=len(files), unit="files"):
        #     if e:
        #         tqdm.write(e)
        # bar.update(1)

        # tqdm.write("Gathering MIDI files...")
        # files = scan(args.input_dir, "**/*_full.mid", False)
        # for e in tqdm(worker_pool.imap_unordered(move_to_output_folder, files), total=len(files), unit="files"):
        #     if e:
        #         tqdm.write(e)
        # bar.update(1)

        # tqdm.write("Splitting into training and test data...")
        # mkdir("train")
        # mkdir("test")
        # files = scan(args.output_dir, "*.mid", False)
        # for file in tqdm(files, total=len(files), unit="files"):
        #     if randint(0, 4): # 25% chance to go into test data
        #         move_to_folder(file, join(args.output_dir, "test"))
        #     else:
        #         move_to_folder(file, join(args.output_dir, "train"))
        # bar.update(1)

        # TODO: Transpose all channels to C major or C minor (possibly A minor)
        # transpose() works, but it does not do the above
        # Approach: we can only extract the key from a midi file, so we do the following:
        # - convert to csv
        # - extract channels as csv
        # - convert csv channels to midi channels
        # - analyze midi channels and get key and tonic
        # - go back to the (still existing) csv channels and transpose them (also transpose the complete csv representation in an extra step)
        # - convert csv channels to midi channels again
        if args.offset != 0:
            tqdm.write("Transposing channels...")
            files = scan(args.input_dir, "**/channel_*.csv", True)
            for e in tqdm(worker_pool.imap_unordered(transpose, files), total=len(files), unit="files"):
                if e:
                    tqdm.write(e)
            bar.update(1)

        # tqdm.write("Converting output data...")
        # files = scan_channel_csv_files()
        # files += scan_track_csv_files()
        # for e in tqdm(worker_pool.imap_unordered(csv_to_midi, files), total=len(files), unit="files"):
        #     if e:
        #         tqdm.write(e)
        # bar.update(1)

        # TODO: do this in another script, this is data prep and not related to splitting MIDI files
        tqdm.write("Converting drum channel...")
        files = scan(args.input_dir, "**/channel_9.csv", True)
        for e in tqdm(worker_pool.imap_unordered(drums_to_bin, files), total=len(files), unit="files"):
            if e:
                tqdm.write(e)
        bar.update(1)

        files = scan(args.output_dir, "*.txt")
        tqdm.write("Merging tracks...")
        with open(join(args.output_dir, "drums.txt"), "w") as out_file:
            for file in files:
                with open(file["path"], "r") as in_file:
                    for line in in_file:
                        out_file.write(line)
        bar.update(1)

        tqdm.write("Finished processing")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split MIDI files into channels and tracks.")
    parser.add_argument("-i", "--input", type=str, dest="input_dir", required=True, metavar="dir", help="(required) The folder containing the input data")
    parser.add_argument("-o", "--output", type=str, dest="output_dir", required=True, metavar="dir", help="(required) The folder containing the output data")
    parser.add_argument("-s", "--shift", type=int, dest="offset", default=0, metavar="N", help="When given, will transpose the entire song by the given amount (half-notes)")
    parser.add_argument("-t", "--threads", type=int, dest="num_threads", default=cpu_count(), metavar="N", help="The amount of threads to use (default: {})".format(cpu_count()))
    parser.add_argument("-n", dest="normalize", action="store_true", help="When active, will normalize songs in a major key to C major and songs in a minor key to A minor")
    parser.add_argument("-v", dest="verbose", action="store_true")
    args = parser.parse_args()

    original_sigint_handler = signal(SIGINT, SIG_IGN)
    worker_pool = Pool(args.num_threads)
    signal(SIGINT, original_sigint_handler)

    check(args)

    try:
        main(args)
    except KeyboardInterrupt:
        print("Received SIGINT, terminating...")
        worker_pool.terminate()
    else:
        worker_pool.close()

    worker_pool.join()
