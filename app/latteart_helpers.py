from __future__ import absolute_import
import tensorflow as tf
import sys
import os
import shutil
from os import listdir
from os import mkdir
from shutil import copyfile
from os.path import isfile, join
import glob
import argparse
import logging
import subprocess
import time
import random
import urllib3
from . import yelp_helper
# from . import creds

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#API_KEY = creds.login['api_key']
API_KEY = os.environ.get('API_KEY')

# top two functions not being used currenrly
def load_graph(model_file):
    graph = tf.Graph()
    graph_def = tf.GraphDef()

    with open(model_file, "rb") as f:
        graph_def.ParseFromString(f.read())
    with graph.as_default():
        tf.import_graph_def(graph_def)

    return graph

def load_labels(label_file):
    label = []
    proto_as_ascii_lines = tf.gfile.GFile(label_file).readlines()
    for l in proto_as_ascii_lines:
        label.append(l.rstrip())
    return label

def label_image(image_path, model_dir):
    """Function used to label an image

    Args:
        argv[1]: path to image

    Returns:
        Returns a score 

    Todo:
        make latteart directory a paramaeter
        test with non jpeg images
    """

    # Read in the image_data
    image_data = tf.gfile.FastGFile(image_path, 'rb').read()

    # Load label file and strip off carriage return
    label_lines = [line.rstrip() for line 
                       in tf.gfile.GFile(model_dir + "retrained_labels.txt")]

    # Unpersist graph from file
    with tf.gfile.FastGFile(model_dir + "retrained_graph.pb", 'rb') as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())
        _ = tf.import_graph_def(graph_def, name='')

    with tf.Session() as sess:
        # Feed the image_data as input to the graph and get first prediction
        softmax_tensor = sess.graph.get_tensor_by_name('final_result:0')
        
        predictions = sess.run(softmax_tensor, \
                 {'DecodeJpeg/contents:0': image_data})
        
        # Sort to show labels of first prediction in order of confidence
        top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]

        # Get prediction score for positive class
        positive_score = round(predictions[0][1],2)
        logger.info('Score is %s', positive_score)
        return positive_score


        # code for printing out probability for both classes
        #for node_id in top_k:
        #    human_string = label_lines[node_id]
        #    score = predictions[0][node_id]
        #    print('%s (score = %.5f)' % (human_string, score))


def label_directory(image_path, model_dir, threshold):
    """Function used to label all images in a directory

    Args:
        argv[1]: path to image directory
        argv[2]: model dir
        argv[3]:  threshold above which to classify as art

    Returns:
        Returns two numbers:  # of latte art images, total # of images

    todo:
        make latteart directory a paramaeter
        add argparse to pass arguments
    """

    # testing new code
    #imgFiles = [f for f in listdir(varPath) if isfile(join(varPath, f))]
    imgFiles = glob.glob(image_path+'/*.jpg')

    # load urls for each image
    url_file = image_path + '/log.txt'
    url_for_imgfile = dict(line.rstrip('\n').split(',') for line in open(url_file))

    
    # Loads label file, strips off carriage return
    label_lines = [line.rstrip() for line 
                       in tf.gfile.GFile(model_dir + "/retrained_labels.txt")]

    # Unpersists graph from file
    with tf.gfile.FastGFile(model_dir + "/retrained_graph.pb", 'rb') as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())
        _ = tf.import_graph_def(graph_def, name='')

    with tf.Session() as sess:
        # Feed the image_data as input to the graph and get first prediction
        softmax_tensor = sess.graph.get_tensor_by_name('final_result:0')    
        img_count = 0
        positive_count = 0
        score_for_url = {}
        output_list= []
        for imageFile in imgFiles:
            image_data = tf.gfile.FastGFile(imageFile, 'rb').read()
            predictions = sess.run(softmax_tensor, \
                 {'DecodeJpeg/contents:0': image_data})
            # Sort to show labels of first prediction in order of confidence
            top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]
            # Get prediction score for positive class
            positive_score = round(predictions[0][1],2)
            logger.info('Score for %s is %s', imageFile, positive_score)
            #positive_score = label_image(imageFile, model_dir)
            score_for_url[url_for_imgfile[os.path.basename(imageFile)]] = positive_score
            if (positive_score > threshold):
                positive_count+=1
                #score_for_url[url_for_imgfile[os.path.basename(imageFile)]] = positive_score
            img_count += 1

        return score_for_url, positive_count, img_count
        
def is_ascii(s):
    return all(ord(c) < 128 for c in s)

def rank_bizs_in_location(location, num_of_businesses_to_get, model_dir, tmpimgdir, threshold):
    """Function used to get scores for num_of_businesses_to_get businesses in a location

    Args:
        location: location (can be city, zip, lat long string)
        num_of_businesses_to_get: number of business to get and score

    Returns:
        Returns three arrays - positive_counts, total_counts, biz_names
    """

    if location is None:
        location = "chicago"

    logger.info('Starting to get %s businesses in %s', num_of_businesses_to_get, location)
    all_bizids = yelp_helper.get_business_ids_from_api(location, num_of_businesses_to_get)
    
    # remove businesses with non ascii characters
    clean_bizids =  [b for b in all_bizids if is_ascii(b)]
    logger.info('Got %s businesses in %s', len(clean_bizids), location)

    if len(clean_bizids) > 0:
        positive_counts = {}  #store number of positive images for the business
        total_counts = {} # store total number of imageas retrieved for the business
        biz_names = {} # store the business name
        for biz in clean_bizids:
            bizresponse = yelp_helper.get_business(API_KEY, biz)
            bizname = bizresponse['name']
            logger.info('Processing %s', bizname)
            bizurl = 'http://www.yelp.com/biz/' + biz
            num_images = 0
            positive_count = 0
            logger.info('Getting images for id %s name %s and putting them in %s', biz, bizname, tmpimgdir)
            num_images = yelp_helper.get_business_images(biz, tmpimgdir)
            logger.info('Labeling %s images in directory %s with threshold %s', num_images, tmpimgdir, threshold)
            if num_images:
                score_for_url, positive_count, img_count = label_directory(tmpimgdir, model_dir, threshold)
            else:
                positive_count = 0
            
            positive_counts[bizurl]= positive_count
            total_counts[bizurl]= num_images
            biz_names[bizurl] = bizname
            logger.info('%s has %s//%s arts', bizname, positive_count, img_count)
            wait_time = random.randint(1, 5)
            logger.info('waiting %s seconds to process next business...',wait_time)
            time.sleep(wait_time)
        return positive_counts, total_counts, biz_names
    else:
        logger.error('No businesses returned by get_business_ids_from_api', exc_info=True)
        return 0;


