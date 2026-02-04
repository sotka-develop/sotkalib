import inspect


class ArgsIncludedError(Exception):
	def __init__(self, *args, stack_depth: int = 2):
		_args = args
		stack_args_to_exc = []
		frames = inspect.stack()[1:-1][::-1][:stack_depth]
		for frame_info in frames:
			frame = frame_info.frame
			args, _, _, values = inspect.getargvalues(frame)
			f_locals = frame.f_locals
			args_with_values = {arg: values[arg] for arg in args}
			stack_args_to_exc.append(args_with_values | f_locals | {"frame_name": frame.f_code.co_name})
		super().__init__(*_args, *stack_args_to_exc)
