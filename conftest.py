import view.view_output
from unittest.mock import Mock

view.view_output.show_message = Mock()
view.view_output.show_warning = Mock()
view.view_output.show_error = Mock()
view.view_output.ask_confirmation = Mock(return_value=True)