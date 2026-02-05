import datetime
import random
import time
from io import StringIO
from pathlib import Path
from random import randint
from typing import Any

import yappi

from sotkalib.json.dump import safe_serialize_value
from sotkalib.log import get_logger


def generate_test_data(depth: int = 5, branching: int = 3) -> Any:
	data: Any

	data_type = random.choice(
		["primitive", "dict", "list", "nested_dict", "nested_list", "complex_object", "circular_ref"]
	)

	if depth == 0 or data_type == "primitive":
		return random.choice(
			[
				None,
				random.randint(-1000000, 1000000),
				random.uniform(-1000000, 1000000),
				random.random(),
				random.choice([True, False]),
				str(random.random()),
				str(random.randint(-1000000, 1000000)),
			]
		)
	elif data_type == "dict":
		return {f"key_{i}": generate_test_data(depth - 1, branching) for i in range(random.randint(1, branching))}
	elif data_type == "list":
		return [generate_test_data(depth - 1, branching) for _ in range(random.randint(1, branching))]
	elif data_type == "nested_dict":
		return {
			f"level_{i}": generate_test_data(depth - 1, branching)
			for i in range(random.randint(1, max(1, branching // 2)))
		}
	elif data_type == "nested_list":
		return [generate_test_data(depth - 1, branching) for _ in range(random.randint(1, max(1, branching // 2)))]
	elif data_type == "complex_object":

		class ComplexObject:
			pass

		obj = ComplexObject()
		obj.attr1 = generate_test_data(depth - 1, branching)
		obj.attr2 = generate_test_data(depth - 1, branching)
		obj.nested = generate_test_data(depth - 1, branching)

		return obj
	elif data_type == "circular_ref":

		class Circular:
			pass

		obj = Circular()
		obj.self = obj
		obj.data = generate_test_data(depth - 1, branching)

		return obj


def test_safe_serialize_stress(iterations: int = 5000, max_depth: int = 10):
	get_logger().info(f"\nStarting stress test with {iterations} iterations...")
	get_logger().info(f"Max depth: {max_depth}")
	get_logger().info("-" * 50)

	get_logger().info("Warming up...")

	warmup_data = generate_test_data(max_depth)
	for _ in range(100):
		safe_serialize_value(warmup_data)

	get_logger().info("Warm up complete.")
	get_logger().info("-" * 50)

	yappi.start()
	yappi.clear_stats()

	start_time = time.time()

	for i in range(iterations):
		data = generate_test_data(random.randint(1, max_depth), random.randint(1, 5))

		try:
			safe_serialize_value(data)
		except Exception as e:
			get_logger().info(f"Error on iteration {i}: {e}")
			get_logger().info(f"Data type: {type(data)}")
			raise

	end_time = time.time()

	yappi.stop()
	func_stats = yappi.get_func_stats()
	thread_stats = yappi.get_thread_stats()

	elapsed = end_time - start_time
	avg_time = elapsed / iterations

	get_logger().info("\nTest completed!")
	get_logger().info(f"Total time: {elapsed:.4f} seconds")
	get_logger().info(f"Average time per call: {avg_time:.6f} seconds")
	get_logger().info(f"Calls per second: {iterations / elapsed:.0f}")

	if avg_time > 0.001:
		get_logger().info(f"\nWARNING: Average time per call is high ({avg_time:.6f}s). Consider further optimization.")
	elif avg_time > 0.0001:
		get_logger().info(f"\nPerformance is acceptable but could be improved ({avg_time:.6f}s).")
	else:
		get_logger().info(f"\nExcellent performance ({avg_time:.6f}s)!")

	get_logger().info("\n--- Yappi Profiling Results ---")

	get_logger().info("\nTop functions by wall time:")
	p = Path("tmp/")
	p.mkdir(exist_ok=True)

	func_stats.save(f"tmp/fstat_{datetime.date.today().isoformat()}_{randint(0, 10)}.pstat", type="pstat")
	output = StringIO()
	func_stats.print_all(
		columns={0: ("name", 100), 1: ("ncall", 15), 2: ("tsub", 15), 3: ("ttot", 15), 4: ("tavg", 15)}, out=output
	)
	output.seek(0)
	with open(f"tmp/func_stats_{datetime.date.today().isoformat()}_{randint(0, 10)}.txt", "w") as f:
		f.write(output.getvalue())

	get_logger().info("\nTop thr by wall time:")
	output = StringIO()
	thread_stats.print_all(out=output)
	output.seek(0)
	with open(f"tmp/thr_stats_{datetime.date.today().isoformat()}_{randint(0, 10)}.txt", "w") as f:
		f.write(output.getvalue())

	assert iterations > 0
	assert elapsed > 0
