class DoesNotImplementError(BaseException):
	violations: list[str]
	proto: type
	target: type

	def __init__(self, violations: list[str], proto: type, failed: type, *args):
		super().__init__(*args)
		self.violations = violations
		self.proto = proto
		self.target = failed

	def __repr__(self) -> str:
		return (
			(
				f"DoesNotImplementError<type=`{self.target.__name__}` does not implement protocol_class=`{self.proto.__name__}`>"
				"\n(violations="
				'\n... "'
			)
			+ '"\n... "'.join(self.violations)
			+ '")'
		)

	__str__ = __repr__
