""" Filename:     replier.py
    Author(s):    Fina Polat
    Description:  Thomas Bellucci's replier NPS is replaced with Cosine Similarity.
    Date created: Dec. 1st, 2021
"""

import random

import numpy as np
from cltl.combot.backend.utils.casefolding import casefold_capsule
from cltl.reply_generation.api import BasicReplier
from cltl.reply_generation.data.sentences import (CONFLICTING_KNOWLEDGE,
                                                  CURIOSITY,
                                                  EXISTING_KNOWLEDGE, HAPPY,
                                                  NEW_KNOWLEDGE, NO_ANSWER,
                                                  NO_TRUST, TRUST)
from cltl.reply_generation.utils.helper_functions import lexicon_lookup
from replier_utils import thoughts_from_brain
from sentence_transformers import SentenceTransformer
from sentence_transformers import util as sent_util

model = SentenceTransformer("multi-qa-mpnet-base-cos-v1")
model.save("sbert_models")


class SimReplier(BasicReplier):
    def __init__(self):
        """Creates a replier to respond to questions and statements by the
        user. Statements are replied to by phrasing a thought. Selection
        of the thoughts is performed through Next Sentence Prediction (NSP).

        params
        object brain:  the brain of Leolani
        str savefile:  file with a pretrained BERT NSP model

        returns: None
        """

        super(SimReplier, self).__init__()

    def reply_to_statement(self, brain_response):
        """Selects a Thought from the brain response to verbalize.

        params
        dict brain_response: brain response from brain.update() converted to JSON

        returns: a string representing a verbalized thought
        """
        utterance = casefold_capsule(brain_response["statement"], format="natural")
        context = brain_response["context"]

        # Extract thoughts from brain response
        thoughts = thoughts_from_brain(brain_response)

        # Score phrasings of thoughts
        best_response = None
        best_score = -np.inf

        for thought_descr, (thought_type, thought_info) in thoughts.items():

            # preprocess
            thought_info = casefold_capsule(
                {"thought": thought_info}, format="natural"
            )["thought"]

            say = None
            if thought_type == "_complement_conflict":
                say = self._phrase_cardinality_conflicts(thought_info, utterance)

            elif thought_type == "_negation_conflicts":
                say = self._phrase_negation_conflicts(thought_info, utterance)

            elif thought_type == "_statement_novelty":
                say = self._phrase_statement_novelty(thought_info, utterance)

            elif thought_type == "_entity_novelty":
                say = self._phrase_entity_novelty(thought_info, utterance)

            elif thought_type == "_complement_gaps":
                say = self._phrase_complement_gaps(thought_info, utterance)

            elif thought_type == "_subject_gaps":
                say = self._phrase_subject_gaps(thought_info, utterance)

            elif thought_type == "_overlaps":
                say = self._phrase_overlaps(thought_info, utterance)

            elif thought_type == "_trust":
                say = self._phrase_trust(thought_info)

            if say is None:  # Fallback strategy
                say = self._phrase_fallback()
            say = say.replace("-", " ").replace("  ", " ")

            # Score response (say) w.r.t. context
            # context = utterance['utterance']

            score, sim_reply = self._get_similarity_score(context, say, model=model)
            # print(f'context: {context}')
            # print(f'say:{say}')
            # print(f'Sim reply: {sim_reply}')
            # print(score)
            if score > best_score:
                best_score = score
                best_response = sim_reply

        print("\nRESPONSE SCORE", best_score)
        print(f"inside context: {context}")
        # print("\nRESPONSE", best_response)

        return best_response

    def new_reply_to_statement(self, brain_response, model=model):
        # utterance = casefold_capsule(brain_response['statement'], format='natural')
        utterance = brain_response["utterance"]
        context = brain_response["context"]

        if context == "":
            context = utterance
        print(context)

        cand_list = self.get_candidates(brain_response)
        print(len(cand_list))
        print(cand_list)
        ref_embedding = model.encode(context, convert_to_tensor=True)
        similarity_dict = dict()
        for cand in cand_list:
            candidate_embedding = model.encode(cand, convert_to_tensor=True)
            similarity = sent_util.cos_sim(ref_embedding, candidate_embedding)
            similarity_dict[cand] = 1 - similarity

        reply = max(similarity_dict, key=similarity_dict.get)
        explanation = sorted(
            similarity_dict.items(), key=lambda item: item[1], reverse=True
        )
        print(explanation)

        return reply

    @staticmethod
    def _get_similarity_score(utterance, say, model=model):
        sentence1_embeddings = model.encode(utterance)
        candidate_embedding = model.encode(say)
        similarity = sent_util.cos_sim(sentence1_embeddings, candidate_embedding)
        similarity = 1 - similarity
        return similarity, say

    def get_candidates(self, brain_response):
        """Create a list of all verbalized thoughts as LenkaReplier would.

        params
        dict brain_response: brain response from brain.update() converted to JSON

        returns: a list of all verbalized thought
        """
        utterance = casefold_capsule(brain_response["statement"], format="natural")
        # Extract thoughts from brain response
        thoughts = thoughts_from_brain(brain_response)
        cand_list = list()

        for thought_descr, (thought_type, thought_info) in thoughts.items():

            # preprocess
            thought_info = casefold_capsule(
                {"thought": thought_info}, format="natural"
            )["thought"]
            say = None
            if thought_type == "_complement_conflict":
                say = self._phrase_cardinality_conflicts(thought_info, utterance)

            elif thought_type == "_negation_conflicts":
                say = self._phrase_negation_conflicts(thought_info, utterance)

            elif thought_type == "_statement_novelty":
                say = self._phrase_statement_novelty(thought_info, utterance)

            elif thought_type == "_entity_novelty":
                say = self._phrase_entity_novelty(thought_info, utterance)

            elif thought_type == "_complement_gaps":
                say = self._phrase_complement_gaps(thought_info, utterance)

            elif thought_type == "_subject_gaps":
                say = self._phrase_subject_gaps(thought_info, utterance)

            elif thought_type == "_overlaps":
                say = self._phrase_overlaps(thought_info, utterance)

            elif thought_type == "_trust":
                say = self._phrase_trust(thought_info)

            if say is None:  # Fallback strategy
                say = self._phrase_fallback()

            say = say.replace("-", " ").replace("  ", " ")

            cand_list.append(say)

        return cand_list

    def _phrase_cardinality_conflicts(self, conflicts, utterance):
        """Phrases a cardinality conflict thought.

        params:
        dict conflicts: thoughts
        dict utterance: an utterance

        returns: phrase
        """
        say = random.choice(CONFLICTING_KNOWLEDGE)
        conflict = random.choice(conflicts)
        x = (
            "you"
            if conflict["_provenance"]["_author"] == utterance["author"]
            else conflict["_provenance"]["_author"]
        )
        y = (
            "you"
            if utterance["triple"]["_subject"]["_label"]
            == conflict["_provenance"]["_author"]
            else utterance["triple"]["_subject"]["_label"]
        )

        # Checked
        say += " %s told me in %s that %s %s %s, but now you tell me that %s %s %s" % (
            x,
            conflict["_provenance"]["_date"],
            y,
            utterance["triple"]["_predicate"]["_label"],
            conflict["_complement"]["_label"],
            y,
            utterance["triple"]["_predicate"]["_label"],
            utterance["triple"]["_complement"]["_label"],
        )

        return say

    def _phrase_negation_conflicts(self, conflicts, utterance):
        """Phrases a negation conflict thought.

        params:
        dict conflicts: thoughts
        dict utterance: an utterance

        returns: phrase
        """
        # Separate positive and negative polarities
        affirmative_conflict = [
            item for item in conflicts if item["_polarity_value"] == "POSITIVE"
        ]
        negative_conflict = [
            item for item in conflicts if item["_polarity_value"] == "NEGATIVE"
        ]

        # There is a conflict, so we phrase it
        say = "I am forgetting something"

        if affirmative_conflict and negative_conflict:
            say = random.choice(CONFLICTING_KNOWLEDGE)

            affirmative_conflict = random.choice(affirmative_conflict)
            negative_conflict = random.choice(negative_conflict)

            say += (
                " %s told me in %s that %s %s %s, but in %s %s told me that %s did not %s %s"
                % (
                    affirmative_conflict["_provenance"]["_author"],
                    affirmative_conflict["_provenance"]["_date"],
                    utterance["triple"]["_subject"]["_label"],
                    utterance["triple"]["_predicate"]["_label"],
                    utterance["triple"]["_complement"]["_label"],
                    negative_conflict["_provenance"]["_date"],
                    negative_conflict["_provenance"]["_author"],
                    utterance["triple"]["_subject"]["_label"],
                    utterance["triple"]["_predicate"]["_label"],
                    utterance["triple"]["_complement"]["_label"],
                )
            )
        return say

    def _phrase_statement_novelty(self, prev_claims, utterance):
        """Phrases a statement novelty thought.

        params:
        dict prev_claims: thoughts
        dict utterance:   an utterance

        returns: phrase
        """
        # I already knew this
        if prev_claims:
            say = random.choice(EXISTING_KNOWLEDGE)
            prev_claim = random.choice(prev_claims)

            say += " %s told me about it in %s" % (
                prev_claim["_provenance"]["_author"],
                prev_claim["_provenance"]["_date"],
            )

        # New claim
        else:
            entity_role = random.choice(["subject", "object"])

            say = random.choice(NEW_KNOWLEDGE)

            if entity_role == "subject":
                if "person" in " or ".join(
                    utterance["triple"]["_complement"]["_types"]
                ):
                    any_type = "anybody"
                elif "location" in " or ".join(
                    utterance["triple"]["_complement"]["_types"]
                ):
                    any_type = "anywhere"
                else:
                    any_type = "anything"

                # Checked
                say += " I did not know %s that %s %s" % (
                    any_type,
                    utterance["triple"]["_subject"]["_label"],
                    utterance["triple"]["_predicate"]["_label"],
                )

            elif entity_role == "object":
                # Checked
                say += " I did not know anybody who %s %s" % (
                    utterance["triple"]["_predicate"]["_label"],
                    utterance["triple"]["_complement"]["_label"],
                )
        return say

    def _phrase_entity_novelty(self, novelties, utterance):
        """Phrases an entity novelty thought.

        params:
        dict novelties: thoughts
        dict utterance: an utterance

        returns: phrase
        """
        # Select object or subject whichever is available
        if novelties["_subject"]:
            entity_role = "subject"
            entity_label = utterance["triple"]["_subject"]["_label"]
        else:
            entity_role = "object"
            entity_label = utterance["triple"]["_complement"]["_label"]

        # Phrase
        entity_label = self._replace_pronouns(
            utterance["author"], entity_label=entity_label, role=entity_role
        )
        say = random.choice(NEW_KNOWLEDGE)
        if entity_label != "you":  # TODO or type person?
            # Checked
            say += " I had never heard about %s before!" % self._replace_pronouns(
                utterance["author"], entity_label=entity_label, role="object"
            )
        else:
            say += " I am excited to get to know about %s!" % entity_label

        return say

    def _phrase_subject_gaps(self, all_gaps, utterance):
        """Phrases a subject gap thought.

        params:
        dict all_gaps:  thoughts
        dict utterance: an utterance

        returns: phrase
        """
        # Select object or subject to pursue
        if all_gaps["_subject"]:
            entity_role = "subject"
            gaps = all_gaps["_subject"]
        else:
            entity_role = "object"
            gaps = all_gaps["_complement"]

        say = random.choice(CURIOSITY)

        if entity_role == "subject":

            if not gaps:
                say += " What types can %s %s" % (
                    utterance["triple"]["_subject"]["_label"],
                    utterance["triple"]["_predicate"]["_label"],
                )
            else:
                gap = random.choice(gaps)

                if (
                    "is " in gap["_predicate"]["_label"]
                    or " is" in gap["_predicate"]["_label"]
                ):
                    say += " Is there a %s that %s %s?" % (
                        " or".join(gap["_entity"]["_types"]),
                        gap["_predicate"]["_label"],
                        utterance["triple"]["_subject"]["_label"],
                    )
                elif " of" in gap["_predicate"]["_label"]:
                    say += " Is there a %s that %s is %s?" % (
                        " or".join(gap["_entity"]["_types"]),
                        utterance["triple"]["_subject"]["_label"],
                        gap["_predicate"]["_label"],
                    )

                elif " " in gap["_predicate"]["_label"]:
                    say += " Is there a %s that is %s %s?" % (
                        " or".join(gap["_entity"]["_types"]),
                        gap["_predicate"]["_label"],
                        utterance["triple"]["_subject"]["_label"],
                    )
                else:
                    # Checked
                    say += " Has %s %s %s?" % (
                        utterance["triple"]["_subject"]["_label"],
                        gap["_predicate"]["_label"],
                        " or".join(gap["_entity"]["_types"]),
                    )
        else:
            if not gaps:
                say += " What kinds of things can %s a %s like %s" % (
                    utterance["triple"]["_predicate"]["_label"],
                    utterance["triple"]["_complement"]["_label"],
                    utterance["triple"]["_subject"]["_label"],
                )
            else:
                gap = random.choice(gaps)

                if "#" in " or".join(gap["_entity"]["_types"]):
                    say += " What is %s %s?" % (
                        utterance["triple"]["_subject"]["_label"],
                        gap["_predicate"]["_label"],
                    )
                elif " " in gap["_predicate"]["_label"]:
                    # Checked
                    say += " Has %s ever %s %s?" % (
                        " or".join(gap["_entity"]["_types"]),
                        gap["_predicate"]["_label"],
                        utterance["triple"]["_subject"]["_label"],
                    )

                else:
                    # Checked
                    say += " Has %s ever %s a %s?" % (
                        utterance["triple"]["_subject"]["_label"],
                        gap["_predicate"]["_label"],
                        " or".join(gap["_entity"]["_types"]),
                    )
        return say

    def _phrase_complement_gaps(self, all_gaps, utterance):
        """Phrases a object gap (complement gap) thought.

        params:
        dict all_gaps:  thoughts
        dict utterance: an utterance

        returns: phrase
        """
        # Select object or subject to pursue
        if all_gaps["_subject"]:
            entity_role = "subject"
            gaps = all_gaps["_subject"]
        else:
            entity_role = "object"
            gaps = all_gaps["_complement"]

        thought = None
        say = random.choice(CURIOSITY)

        if entity_role == "subject":

            if not gaps:
                say += " What types can %s %s" % (
                    utterance["triple"]["_subject"]["_label"],
                    utterance["triple"]["_predicate"]["_label"],
                )
            else:
                gap = random.choice(gaps)

                if (
                    " in" in gap["_predicate"]["_label"]
                ):  # ' by' in gap['_predicate']['_label']
                    say += " Is there a %s %s %s?" % (
                        " or".join(gap["_entity"]["_types"]),
                        gap["_predicate"]["_label"],
                        utterance["triple"]["_complement"]["_label"],
                    )
                else:
                    say += " Has %s %s by a %s?" % (
                        utterance["triple"]["_complement"]["_label"],
                        gap["_predicate"]["_label"],
                        " or".join(gap["_entity"]["_types"]),
                    )
        else:  # object
            if not gaps:
                otypes = (
                    " or".join(utterance["triple"]["_complement"]["_types"])
                    if " or".join(utterance["triple"]["_complement"]["_types"]) != ""
                    else "things"
                )
                stypes = (
                    " or".join(utterance["triple"]["_subject"]["_types"])
                    if " or ".join(utterance["triple"]["_subject"]["_types"]) != ""
                    else "actors"
                )
                say += " What types of %s like %s do %s usually %s" % (
                    otypes,
                    utterance["triple"]["_complement"]["_label"],
                    stypes,
                    utterance["triple"]["_predicate"]["_label"],
                )
            else:
                gap = random.choice(gaps)

                if "#" in " or".join(gap["_entity"]["_types"]):
                    say += " What is %s %s?" % (
                        utterance["triple"]["_complement"]["_label"],
                        gap["_predicate"]["_label"],
                    )
                elif " by" in gap["_predicate"]["_label"]:
                    say += " Has %s ever %s a %s?" % (
                        utterance["triple"]["_complement"]["_label"],
                        gap["_predicate"]["_label"],
                        " or".join(gap["_entity"]["_types"]),
                    )
                else:
                    say += " Has a %s ever %s %s?" % (
                        " or".join(gap["_entity"]["_types"]),
                        gap["_predicate"]["_label"],
                        utterance["triple"]["_complement"]["_label"],
                    )
        return say

    @staticmethod
    def _phrase_overlaps(all_overlaps, utterance):
        # type: (dict, dict) -> str

        entity_role = random.choice(["subject", "object"])
        overlaps = (
            all_overlaps["_subject"]
            if entity_role == "subject"
            else all_overlaps["_complement"]
        )
        say = None

        if not overlaps:
            say = None

        elif len(overlaps) < 2 and entity_role == "subject":
            say = random.choice(HAPPY)

            say += " Did you know that %s also %s %s" % (
                utterance["triple"]["_subject"]["_label"],
                utterance["triple"]["_predicate"]["_label"],
                random.choice(overlaps)["_entity"]["_label"],
            )

        elif len(overlaps) < 2 and entity_role == "object":
            say = random.choice(HAPPY)

            say += " Did you know that %s also %s %s" % (
                random.choice(overlaps)["_entity"]["_label"],
                utterance["triple"]["_predicate"]["_label"],
                utterance["triple"]["_complement"]["_label"],
            )

        elif entity_role == "subject":
            say = random.choice(HAPPY)
            sample = random.sample(overlaps, 2)

            entity_0 = sample[0]["_entity"]["_label"]
            entity_1 = sample[1]["_entity"]["_label"]

            say += " Now I know %s items that %s %s, like %s and %s" % (
                len(overlaps),
                utterance["triple"]["_subject"]["_label"],
                utterance["triple"]["_predicate"]["_label"],
                entity_0,
                entity_1,
            )

        elif entity_role == "object":
            say = random.choice(HAPPY)
            sample = random.sample(overlaps, 2)
            types = (
                " or ".join(sample[0]["_entity"]["_types"])
                if sample[0]["_entity"]["_types"]
                else "things"
            )
            say += " Now I know %s %s that %s %s, like %s and %s" % (
                len(overlaps),
                types,
                utterance["triple"]["_predicate"]["_label"],
                utterance["triple"]["_complement"]["_label"],
                sample[0]["_entity"]["_label"],
                sample[1]["_entity"]["_label"],
            )

        return say

    def _phrase_trust(self, trust):
        """Phrases the trust of the robot w.r.t. the speaker.

        params:
        str trust: trust value for the speaker

        returns: phrase
        """
        if float(trust) > 0.75:  # bugfix
            say = random.choice(TRUST)
        else:
            say = random.choice(NO_TRUST)

        return say

    def _phrase_fallback(self):
        """Phrases a fallback utterance when an error has ocurred or no
        thoughts were generated.

        returns: phrase
        """
        return "I do not know what to say."

    ## Did not touch!
    def reply_to_question(self, brain_response):
        say = ""
        previous_author = ""
        previous_predicate = ""
        gram_person = ""
        gram_number = ""

        utterance = brain_response["question"]
        response = brain_response["response"]

        # TODO revise (we conjugate the predicate by doing this)
        utterance = casefold_capsule(utterance, format="natural")

        if not response:
            subject_types = (
                " or ".join(utterance["subject"]["type"])
                if utterance["subject"]["type"] is not None
                else ""
            )
            object_types = (
                " or ".join(utterance["object"]["type"])
                if utterance["object"]["type"] is not None
                else ""
            )

            if subject_types and object_types and utterance["predicate"]["label"]:
                say += "I know %s usually %s %s, but I do not know this case" % (
                    random.choice(utterance["subject"]["type"]),
                    str(utterance["predicate"]["label"]),
                    random.choice(utterance["object"]["type"]),
                )
                return say

            else:
                return random.choice(NO_ANSWER)

        # Each triple is hashed, so we can figure out when we are about the say things double
        handled_items = set()
        response.sort(key=lambda x: x["authorlabel"]["value"])

        for item in response:

            # INITIALIZATION
            subject, predicate, object = self._assign_spo(utterance, item)

            author = self._replace_pronouns(
                utterance["author"], author=item["authorlabel"]["value"]
            )
            subject = self._replace_pronouns(
                utterance["author"], entity_label=subject, role="subject"
            )
            object = self._replace_pronouns(
                utterance["author"], entity_label=object, role="object"
            )

            subject = self._fix_entity(subject, utterance["author"])
            object = self._fix_entity(object, utterance["author"])

            # Hash item such that duplicate entries have the same hash
            item_hash = "{}_{}_{}_{}".format(subject, predicate, object, author)

            # If this hash is already in handled items -> skip this item and move to the next one
            if item_hash in handled_items:
                continue
            # Otherwise, add this item to the handled items (and handle item the usual way (with the code below))
            else:
                handled_items.add(item_hash)

            # Get grammatical properties
            subject_entry = lexicon_lookup(subject.lower())
            if subject_entry and "person" in subject_entry:
                gram_person = subject_entry["person"]
            if subject_entry and "number" in subject_entry:
                gram_number = subject_entry["number"]

            # Deal with author
            say, previous_author = self._deal_with_authors(
                author, previous_author, predicate, previous_predicate, say
            )

            if predicate.endswith("is"):

                say += object + " is"
                if (
                    utterance["object"]["label"].lower() == utterance["author"].lower()
                    or utterance["subject"]["label"].lower()
                    == utterance["author"].lower()
                ):
                    say += " your "
                elif (
                    utterance["object"]["label"].lower() == "leolani"
                    or utterance["subject"]["label"].lower() == "leolani"
                ):
                    say += " my "
                say += predicate[:-3]

                return say

            else:  # TODO fix_predicate_morphology
                be = {"first": "am", "second": "are", "third": "is"}
                if predicate == "be":  # or third person singular
                    if gram_number:
                        if gram_number == "singular":
                            predicate = be[gram_person]
                        else:
                            predicate = "are"
                    else:
                        # TODO: Is this a good default when 'number' is unknown?
                        predicate = "is"
                elif gram_person == "third" and "-" not in predicate:
                    predicate += "s"

                if (
                    item["certaintyValue"]["value"] != "CERTAIN"
                ):  # TODO extract correct certainty marker
                    predicate = "maybe " + predicate

                if item["polarityValue"]["value"] != "POSITIVE":
                    if " " in predicate:
                        predicate = (
                            predicate.split()[0] + " not " + predicate.split()[1]
                        )
                    else:
                        predicate = "do not " + predicate

                say += subject + " " + predicate + " " + object

            say += " and "

        say = say[:-5]

        return say.replace("-", " ").replace("  ", " ")

    @staticmethod
    def _assign_spo(utterance, item):
        empty = ["", "unknown", "none"]

        # INITIALIZATION
        predicate = utterance["predicate"]["type"]

        if (
            utterance["subject"]["label"] is None
            or utterance["subject"]["label"].lower() in empty
        ):
            subject = item["slabel"]["value"]
        else:
            subject = utterance["subject"]["label"]

        if (
            utterance["object"]["label"] is None
            or utterance["object"]["label"].lower() in empty
        ):
            object = item["olabel"]["value"]
        else:
            object = utterance["object"]["label"]

        return subject, predicate, object

    @staticmethod
    def _deal_with_authors(author, previous_author, predicate, previous_predicate, say):
        # Deal with author
        if author != previous_author:
            say += author + " told me "
            previous_author = author
        else:
            if predicate != previous_predicate:
                say += " that "

        return say, previous_author

    def _fix_entity(self, entity, speaker):
        new_ent = ""
        if "-" in entity:
            entity_tokens = entity.split("-")

            for word in entity_tokens:
                new_ent += (
                    self._replace_pronouns(speaker, entity_label=word, role="pos") + " "
                )

        else:
            new_ent += self._replace_pronouns(speaker, entity_label=entity)

        entity = new_ent
        return entity

    @staticmethod
    def _replace_pronouns(speaker, author=None, entity_label=None, role=None):
        if entity_label is None and author is None:
            return speaker

        if role == "pos":
            # print('pos', speaker, entity_label)
            if speaker.lower() == entity_label.lower():
                pronoun = "your"
            elif entity_label.lower() == "leolani":
                pronoun = "my"
            else:
                pronoun = entity_label  # third person pos.
            return pronoun

        # Fix author
        elif author is not None and author.lower() not in ["", "unknown", "none"]:
            if speaker.lower() == author.lower():
                pronoun = "you"
            elif author.lower() == "leolani":
                pronoun = "I"
            else:
                pronoun = author.title()

            return pronoun

        # Entity
        if entity_label is not None and entity_label.lower() not in [
            "",
            "unknown",
            "none",
        ]:
            if (
                speaker.lower() in [entity_label.lower(), "speaker"]
                or entity_label == "Speaker"
            ):
                pronoun = "you"
            elif entity_label.lower() == "leolani":
                pronoun = "I"
            else:
                pronoun = entity_label

            return pronoun