import json


class Config(dict):

    def __init__(self, root_path=None, defaults=None):
        '''[summary]

        [description]

        Arguments:
                root_path {Path or str 对象} -- 配置文件父级目录的绝对路径

        Keyword Arguments:
                defaults {dict对象} -- 默认配置 (default: {None})
        '''
        dict.__init__(self, defaults or {})
        self.root_path = root_path

    def from_object(self, obj):
        '''从类对象中加载配置信息

        [description]

        Arguments:
                obj {dict} -- 继承于dict的类对象
        '''
        for key in dir(obj):
            if key.isupper():
                self[key] = getattr(obj, key)
                if str(key) == 'BASE_DIR':
                    self.root_path = self[key]

    def from_json(self, filename, silent=False):
        try:
            filename = self.root_path / filename
        except TypeError as e:
            e.strerror = 'Not found "BASE_DIR" in settings obj. See in www.settings'
            raise

        try:
            with open(filename) as json_file:
                obj = json.loads(json_file.read())
        except IOError as e:
            if silent and e.errno in (errno.ENOENT, errno.EISDIR):
                return False
            e.strerror = 'Unable to load configuration file (%s)' % e.strerror
            raise
        return self.from_mapping(obj)

    def from_mapping(self, *mapping, **kwargs):
        """Updates the config like :meth:`update` ignoring items with non-upper
        keys.

        .. versionadded:: 0.11
        """
        mappings = []
        if len(mapping) == 1:
            if hasattr(mapping[0], 'items'):
                mappings.append(mapping[0].items())
            else:
                mappings.append(mapping[0])
        elif len(mapping) > 1:
            raise TypeError(
                'expected at most 1 positional argument, got %d' % len(mapping)
            )
        mappings.append(kwargs.items())
        for mapping in mappings:
            for (key, value) in mapping:
                if key.isupper():
                    self[key] = value
        return True
