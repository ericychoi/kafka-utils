from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
import sys
from collections import defaultdict
from contextlib import closing

from kafka import KafkaClient
from yelp_kafka.monitoring import get_consumer_offsets_metadata
from yelp_kafka.offsets import set_consumer_offsets

from .offset_manager import OffsetManagerBase


class OffsetRestore(OffsetManagerBase):

    @classmethod
    def setup_subparser(cls, subparsers):
        parser_offset_restore = subparsers.add_parser(
            "offset_restore",
            description="Commit current consumer offsets for consumer group"
            " specified in given json file.",
            add_help=False,
        )
        parser_offset_restore.add_argument(
            "-h",
            "--help",
            action="help",
            help="Show this help message and exit.",
        )
        parser_offset_restore.add_argument(
            "json_file",
            type=str,
            help="Json file containing offset information",
        )
        parser_offset_restore.set_defaults(command=cls.run)

    @classmethod
    def parse_consumer_offsets(cls, json_file):
        """Parse current offsets from json-file."""
        with open(json_file, 'r') as consumer_offsets_json:
            try:
                parsed_offsets = {}
                parsed_offsets_data = json.load(consumer_offsets_json)
                # Create new dict with partition-keys as integers
                parsed_offsets['groupid'] = parsed_offsets_data['groupid']
                parsed_offsets['offsets'] = {}
                offset_data = parsed_offsets_data['offsets']
                for topic, topic_data in offset_data.iteritems():
                    parsed_offsets['offsets'][topic] = {}
                    for partition, offset in topic_data.iteritems():
                        parsed_offsets['offsets'][topic][int(partition)] = offset
                return parsed_offsets
            except ValueError:
                print(
                    "Error: Given consumer-data json data-file {file} could not be "
                    "parsed".format(file=json_file),
                    file=sys.stderr,
                )
                raise

    @classmethod
    def build_new_offsets(cls, client, topics_offset_data, topic_partitions, current_offsets):
        """Build complete consumer offsets from parsed current consumer-offsets
        and lowmarks and highmarks from current-offsets for.
        """
        new_offsets = defaultdict(dict)
        for topic, partitions in topic_partitions.iteritems():
            # Validate current offsets in range of low and highmarks
            # Currently we only validate for positive offsets and warn
            # if out of range of low and highmarks
            for topic_partition_offsets in current_offsets[topic]:
                partition = topic_partition_offsets.partition
                if partition not in topic_partitions[topic]:
                    continue
                lowmark = topic_partition_offsets.lowmark
                highmark = topic_partition_offsets.highmark
                new_offset = topics_offset_data[topic][partition]
                if new_offset < 0:
                    print(
                        "Error: Given offset: {offset} is negative".format(offset=new_offset),
                        file=sys.stderr,
                    )
                    sys.exit(1)
                if new_offset < lowmark or new_offset > highmark:
                    print(
                        "Warning: Given offset {offset} for topic-partition "
                        "{topic}:{partition} is outside the range of lowmark "
                        "{lowmark} and highmark {highmark}".format(
                            offset=new_offset,
                            topic=topic,
                            partition=partition,
                            lowmark=lowmark,
                            highmark=highmark,
                        )
                    )
                new_offsets[topic][partition] = new_offset
        return new_offsets

    @classmethod
    def run(cls, args, cluster_config):
        # Fetch offsets from given json-file
        parsed_consumer_offsets = cls.parse_consumer_offsets(args.json_file)
        # Setup the Kafka client
        with closing(KafkaClient(cluster_config.broker_list)) as client:
            client.load_metadata_for_topics()

            cls.restore_offsets(client, parsed_consumer_offsets)

    @classmethod
    def restore_offsets(cls, client, parsed_consumer_offsets):
        """Fetch current offsets from kafka, validate them against given
        consumer-offsets data and commit the new offsets.

        :param client: Kafka-client
        :param parsed_consumer_offsets: Parsed consumer offset data from json file
        :type parsed_consumer_offsets: dict(group: dict(topic: partition-offsets))
        """
        # Fetch current offsets
        try:
            consumer_group = parsed_consumer_offsets['groupid']
            topics_offset_data = parsed_consumer_offsets['offsets']
            topic_partitions = dict(
                (topic, [partition for partition in offset_data.keys()])
                for topic, offset_data in topics_offset_data.iteritems()
            )
        except IndexError:
            print(
                "Error: Given parsed consumer-offset data {consumer_offsets} "
                "could not be parsed".format(consumer_offsets=parsed_consumer_offsets),
                file=sys.stderr,
            )
            raise
        current_offsets = get_consumer_offsets_metadata(
            client,
            consumer_group,
            topic_partitions,
            False,
        )
        # Build new offsets
        new_offsets = cls.build_new_offsets(
            client,
            topics_offset_data,
            topic_partitions,
            current_offsets,
        )

        # Commit offsets
        consumer_group = parsed_consumer_offsets['groupid']
        set_consumer_offsets(client, consumer_group, new_offsets, raise_on_error=True)
        print("Restored to new offsets {offsets}".format(offsets=dict(new_offsets)))
