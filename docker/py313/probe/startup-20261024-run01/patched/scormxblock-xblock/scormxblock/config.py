# -*- coding: utf-8 -*-
import pkg_resources

class _ScormComponent(object):
    """Hold information of an scorm web content component on Studio page.
    """
    TAG_VIDEO = r'Video'
    TAG_QUIZ = r'Quiz'
    TAG_ELEARNING_AUTHORING_RECORDER= r'eLearning authoring tools'
    # The order of items in `ALL_TAGS` would be used as Tabs order in Author_View
    ALL_TAGS = [TAG_QUIZ, TAG_ELEARNING_AUTHORING_RECORDER, TAG_VIDEO]

    def __init__(self, icon, name, description, tags, paying, site_link, get_scorm_handler):
        """Constructor of Scorm  Web Content Configuration ( Support Image/Icon `SVG` only )
            @param icon:    path of Image SVG
            @type icon:     string
        """
        self.icon = icon
        self.name = name
        self.description = description
        self.tags = list(tags) if isinstance(tags, (list, tuple)) else [tags]
        self.paying = paying
        self.site_link = site_link
        self._get_scorm_handler = get_scorm_handler

        if not all([tag in _ScormComponent.ALL_TAGS for tag in self.tags]):
            raise NameError('Unsupported tags : {}'.format(str(self.tags)))
    def get_tags_set(self):
        return set(self.tags)

    @property
    def svg_image(self):
        """Return svg image description"""
        return self._get_scorm_handler().resource_string(self.icon)

    def __str__(self):
        return self.name


class SupportedScormResources(object):
    """An iterable object definition for listed `Tags` & `Sites`
    """
    _scorm_xblock_singleton = None

    def __init__(self):
        """Initialize scorm resources vector"""
        self._listed_tags = set()
        self._resources = []

        self._add_resource(
            icon='static/images/adope-captivate.svg', name='Adobe Captivate',
            tags=_ScormComponent.TAG_ELEARNING_AUTHORING_RECORDER,
            paying=True,
            site_link=r'https://www.adobe.com/products/captivate.html',
            description=r'Create stunning courses in minutes.'
        )

        self._add_resource(
            icon='static/images/articulate-360.svg', name='Articulate 360',
            tags=_ScormComponent.TAG_ELEARNING_AUTHORING_RECORDER,
            paying=True,
            site_link=r'https://articulate.com/360',
            description=r'Use Storyline 360 to create courses with custom interactivity. Use Rise 360 to create responsive courses right in your web browser.'
        )

        self._add_resource(
            icon='static/images/ispring-suite.svg', name='iSpring Suite',
            tags=_ScormComponent.TAG_ELEARNING_AUTHORING_RECORDER,
            paying=True,
            site_link=r'https://www.ispringsolutions.com/ispring-suite',
            description=r'Create interactive courses and assessments in record time.'
        )

        self._add_resource(
            icon='static/images/kumullus.svg', name='Kumullus',
            tags=[_ScormComponent.TAG_VIDEO, _ScormComponent.TAG_QUIZ],
            paying=True,
            site_link=r'https://kumullus.com/',
            description=r'Add interactive video to your course.'
        )

    def _add_resource(self, *args, **kwargs):
        """Add new Scorm Web Content Configuration to vector"""
        # append get method obj. of xblock instance method
        kwargs['get_scorm_handler'] = self.get_scorm_handler

        scorm_component = _ScormComponent(*args, **kwargs)
        self._listed_tags.update(scorm_component.get_tags_set())
        self._resources.append(scorm_component)

    def __iter__(self):
        """Return an iterable object"""
        return iter(self._resources)

    @property
    def listed_tags(self):
        """Return supported tags which were appended in method def __init__()
        """
        return [tag for tag in _ScormComponent.ALL_TAGS if tag in self._listed_tags]

    @classmethod
    def assign_scorm_handle(cls, obj):
        """Assign instance of scorm web content xblock to a class member
            @param obj:     instance of scorm web content xblock
            @type obj:      ScormContentXBlock
            @return:        instance of xblock
            @rtype:         ScormContentXBlock
        """
        if not cls._scorm_xblock_singleton:
            cls._scorm_xblock_singleton = obj

        return cls._scorm_xblock_singleton

    def get_scorm_handler(self):
        """Return instance of scorm web content xblock"""
        if not SupportedScormResources._scorm_xblock_singleton:
            raise ValueError('Invalid `SupportedScormResources._scorm_xblock_singleton`. (None)')

        return SupportedScormResources._scorm_xblock_singleton


SUPPORTED_SCORM_RESOURCES = SupportedScormResources()
