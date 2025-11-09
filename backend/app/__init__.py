import warnings

warnings.filterwarnings(
	"ignore",
	message=(
		"Type google._upb._message.(MessageMapContainer|ScalarMapContainer) uses PyType_Spec with"
	),
	category=DeprecationWarning,
)
