import os, sys
from pathlib import Path
import shutil
import unittest
from parameterized import parameterized_class

from agentstack.conf import ConfigFile, set_path
from agentstack.exceptions import ValidationError
from agentstack import frameworks
from agentstack._tools import ToolConfig
from agentstack.agents import AgentConfig
from agentstack.tasks import TaskConfig

BASE_PATH = Path(__file__).parent


@parameterized_class([{"framework": framework} for framework in frameworks.SUPPORTED_FRAMEWORKS])
class TestFrameworks(unittest.TestCase):
    def setUp(self):
        self.project_dir = BASE_PATH / 'tmp' / self.framework / 'test_frameworks'

        os.makedirs(self.project_dir)
        os.chdir(self.project_dir)  # importing the crewai module requires us to be in a working directory
        os.makedirs(self.project_dir / 'src')
        os.makedirs(self.project_dir / 'src' / 'config')

        (self.project_dir / 'src' / '__init__.py').touch()

        shutil.copy(BASE_PATH / 'fixtures' / 'agentstack.json', self.project_dir / 'agentstack.json')
        set_path(self.project_dir)
        with ConfigFile() as config:
            config.framework = self.framework

    def tearDown(self):
        shutil.rmtree(self.project_dir)

    def _populate_min_entrypoint(self):
        """This entrypoint does not have any tools or agents."""
        entrypoint_path = frameworks.get_entrypoint_path(self.framework)
        shutil.copy(BASE_PATH / f"fixtures/frameworks/{self.framework}/entrypoint_min.py", entrypoint_path)

    def _populate_max_entrypoint(self):
        """This entrypoint has tools and agents."""
        entrypoint_path = frameworks.get_entrypoint_path(self.framework)
        shutil.copy(BASE_PATH / f"fixtures/frameworks/{self.framework}/entrypoint_max.py", entrypoint_path)

    def _get_test_agent(self) -> AgentConfig:
        shutil.copy(BASE_PATH / 'fixtures' / 'agents_max.yaml', self.project_dir / 'src' / 'config' / 'agents.yaml')
        return AgentConfig('agent_name')

    def _get_test_task(self) -> TaskConfig:
        shutil.copy(BASE_PATH / 'fixtures' / 'tasks_max.yaml', self.project_dir / 'src' / 'config' / 'tasks.yaml')
        return TaskConfig('task_name')

    def _get_test_tool(self) -> ToolConfig:
        return ToolConfig(name='test_tool', category='test', tools=['test_tool'])

    def _get_test_tool_alternate(self) -> ToolConfig:
        return ToolConfig(name='test_tool_alt', category='test', tools=['test_tool_alt'])

    def test_get_framework_module(self):
        module = frameworks.get_framework_module(self.framework)
        assert module.__name__ == f"agentstack.frameworks.{self.framework}"

    def test_framework_module_implements_protocol(self):
        """Assert that the framework implementation has methods for all the protocol methods."""
        protocol = frameworks.FrameworkModule
        module = frameworks.get_framework_module(self.framework)
        for method_name in dir(protocol):
            if method_name.startswith('_'):
                continue
            assert hasattr(module, method_name), f"Method {method_name} not implemented in {self.framework}"

    def test_get_framework_module_invalid(self):
        with self.assertRaises(Exception) as context:
            frameworks.get_framework_module('invalid')

    def test_validate_project(self):
        self._populate_max_entrypoint()
        frameworks.validate_project()

    def test_validate_project_invalid(self):
        self._populate_min_entrypoint()
        with self.assertRaises(ValidationError) as context:
            frameworks.validate_project()

    def test_validate_project_has_agent_no_task_invalid(self):
        self._populate_min_entrypoint()
        frameworks.add_agent(self._get_test_agent())
        with self.assertRaises(ValidationError) as context:
            frameworks.validate_project()

    def test_validate_project_has_task_no_agent_invalid(self):
        self._populate_min_entrypoint()
        frameworks.add_task(self._get_test_task())
        with self.assertRaises(ValidationError) as context:
            frameworks.validate_project()

    def test_get_agent_tool_names(self):
        self._populate_max_entrypoint()
        frameworks.add_tool(self._get_test_tool(), 'test_agent')
        tool_names = frameworks.get_agent_tool_names('test_agent')
        assert tool_names == ['test_tool']

    def test_add_tool(self):
        self._populate_max_entrypoint()
        frameworks.add_tool(self._get_test_tool(), 'test_agent')

        entrypoint_src = open(frameworks.get_entrypoint_path(self.framework)).read()
        assert "*agentstack.tools['test_tool']" in entrypoint_src

    def test_add_tool_duplicate(self):
        """Repeated calls to add_tool should not duplicate the tool."""
        self._populate_max_entrypoint()
        frameworks.add_tool(self._get_test_tool(), 'test_agent')
        frameworks.add_tool(self._get_test_tool(), 'test_agent')
        
        assert len(frameworks.get_agent_tool_names('test_agent')) == 1

    def test_add_tool_invalid(self):
        self._populate_min_entrypoint()
        with self.assertRaises(ValidationError) as context:
            frameworks.add_tool(self._get_test_tool(), 'test_agent')

    def test_remove_tool(self):
        self._populate_max_entrypoint()
        frameworks.add_tool(self._get_test_tool(), 'test_agent')
        frameworks.remove_tool(self._get_test_tool(), 'test_agent')

        entrypoint_src = open(frameworks.get_entrypoint_path(self.framework)).read()
        assert "*agentstack.tools['test_tool']" not in entrypoint_src

    def test_add_multiple_tools(self):
        self._populate_max_entrypoint()
        frameworks.add_tool(self._get_test_tool(), 'test_agent')
        frameworks.add_tool(self._get_test_tool_alternate(), 'test_agent')

        entrypoint_src = open(frameworks.get_entrypoint_path(self.framework)).read()
        assert (  # ordering is not guaranteed
            "*agentstack.tools['test_tool'], *agentstack.tools['test_tool_alt']" in entrypoint_src
            or "*agentstack.tools['test_tool_alt'], *agentstack.tools['test_tool']" in entrypoint_src
        )

    def test_remove_one_tool_of_multiple(self):
        self._populate_max_entrypoint()
        frameworks.add_tool(self._get_test_tool(), 'test_agent')
        frameworks.add_tool(self._get_test_tool_alternate(), 'test_agent')
        frameworks.remove_tool(self._get_test_tool(), 'test_agent')

        entrypoint_src = open(frameworks.get_entrypoint_path(self.framework)).read()
        assert "*agentstack.tools['test_tool']" not in entrypoint_src
        assert "*agentstack.tools['test_tool_alt']" in entrypoint_src
