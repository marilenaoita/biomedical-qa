import json
import os

import tensorflow as tf

from biomedical_qa.data.bioasq_squad_builder import BioAsqSquadBuilder
from biomedical_qa.data.entity_tagger import get_entity_tagger
from biomedical_qa.inference.inference import Inferrer, get_session, get_model
from biomedical_qa.sampling.squad import SQuADSampler
from inference.bioasq import insert_answers

tf.app.flags.DEFINE_string('bioasq_file', None, 'Path to the BioASQ JSON file.')
tf.app.flags.DEFINE_string('out_file', None, 'Path to the output file.')
tf.app.flags.DEFINE_string('model_config', None, 'Comma-separated list of paths to the model configs.')
tf.app.flags.DEFINE_string("devices", "/cpu:0", "Use this device.")

tf.app.flags.DEFINE_integer("batch_size", 32, "Number of examples in each batch.")

tf.app.flags.DEFINE_integer("beam_size", 5, "Beam size used for decoding.")

tf.app.flags.DEFINE_float("list_answer_prob_threshold", 0.04, "Beam size used for decoding.")

tf.app.flags.DEFINE_boolean("preferred_terms", False, "If true, uses preferred terms when available.")

FLAGS = tf.app.flags.FLAGS


def load_dataset(path):

    with open(path) as f:
        bioasq_json = json.load(f)

    squad_json = BioAsqSquadBuilder(bioasq_json, include_answer_spans=False) \
                    .build() \
                    .get_result_object()

    return bioasq_json, squad_json


if __name__ == "__main__":

    devices = FLAGS.devices.split(",")

    sess = get_session()
    models = [get_model(sess, config, devices, scope="model_%d" % i)
              for i, config in enumerate(FLAGS.model_config.split(","))]
    inferrer = Inferrer(models, sess, FLAGS.beam_size)

    # Build sampler from dataset JSON
    bioasq_json, squad_json = load_dataset(FLAGS.bioasq_file)
    tagger = get_entity_tagger()
    sampler = SQuADSampler(None, None, FLAGS.batch_size,
                           inferrer.models[0].embedder.vocab,
                           shuffle=False, dataset_json=squad_json,
                           tagger=tagger)

    contexts = {p["qas"][0]["id"] : p["context_original_capitalization"]
                for p in squad_json["data"][0]["paragraphs"]}
    answers = inferrer.get_predictions(sampler)
    bioasq_json = insert_answers(bioasq_json, answers, FLAGS.list_answer_prob_threshold,
                                 FLAGS.preferred_terms, FLAGS.terms_file)

    os.makedirs(os.path.dirname(FLAGS.out_file), exist_ok=True)
    with open(FLAGS.out_file, "w") as f:
        json.dump(bioasq_json, f, indent=2, sort_keys=True)
