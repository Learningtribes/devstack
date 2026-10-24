# -*- coding: utf-8 -*-


class _ExternalComponent(object):
    """Hold information of an external web content component on Studio page.
    """
    TAG_INFOGRAPHICS = r'Infographics'
    TAG_PRESENTATION = r'Presentation'
    TAG_VIDEO = r'Video'
    TAG_COLLABORATIVE = r'Collaborative'
    TAG_POLL = r'Poll'
    TAG_SCREEN_RECORDER = r'Screen Recorder'
    # The order of items in `ALL_TAGS` would be used as Tabs order in Author_View
    ALL_TAGS = [TAG_COLLABORATIVE, TAG_INFOGRAPHICS, TAG_PRESENTATION, TAG_POLL, TAG_SCREEN_RECORDER, TAG_VIDEO]

    def __init__(self, icon, name, description, tags, paying, site_link, get_externality_handler):
        """Constructor of External Web Content Configuration ( Support Image/Icon `SVG` only )

            @param icon:    path of Image SVG
            @type icon:     string
        """
        self.icon = icon
        self.name = name
        self.description = description
        self.tags = list(tags) if isinstance(tags, (list, tuple)) else [tags]
        self.paying = paying
        self.site_link = site_link
        self._get_externality_handler = get_externality_handler

        if not all([tag in _ExternalComponent.ALL_TAGS for tag in self.tags]):
            raise NameError('Unsupported tags : {}'.format(str(self.tags)))

    def get_tags_set(self):
        return set(self.tags)

    @property
    def svg_image(self):
        """Return svg image description"""
        return self._get_externality_handler().resource_string(self.icon)

    def __str__(self):
        return self.name


class SupportedExternalResources(object):
    """An iterable object definition for listed `Tags` & `Sites`
    """
    _external_xblock_singleton = None

    def __init__(self):
        """Initialize external resources vector"""
        self._listed_tags = set()
        self._resources = []

        self._add_resource(
            icon='static/images/canva.svg', name='Canva',
            tags=_ExternalComponent.TAG_PRESENTATION,
            paying=None,
            site_link=r'https://www.canva.com/',
            description=r'With thousands of professional templates, images and quality content to choose from, get a headstart on bringing your best ideas and work to life.'
        )
        self._add_resource(
            icon='static/images/Genially.svg', name='Genially',
            tags=[_ExternalComponent.TAG_INFOGRAPHICS, _ExternalComponent.TAG_PRESENTATION],
            paying=None,
            site_link=r'https://genial.ly',
            description=r'Genially is an online tool that helps you record and share interactive videos. Users can log social reactions into your content to help you maximize engagement.'
        )
        self._add_resource(
            icon='static/images/H5P.svg', name='H5P',
            tags=[_ExternalComponent.TAG_INFOGRAPHICS, _ExternalComponent.TAG_PRESENTATION, _ExternalComponent.TAG_VIDEO],
            paying=True,
            site_link=r'https://h5p.org/',
            description=r'Create interactive video, presentation or animated content (such as accordion, chart, collage, image slider, dialogue, chart...), using html5 technology.'
        )
        self._add_resource(
            icon='static/images/Loom.svg', name='Loom',
            tags=_ExternalComponent.TAG_SCREEN_RECORDER,
            paying=None,
            site_link=r'https://www.loom.com/',
            description=r'Record quick videos of your screen and cam.'
        )
        self._add_resource(
            icon='static/images/Padlet.svg', name='Padlet',
            tags=[_ExternalComponent.TAG_COLLABORATIVE, _ExternalComponent.TAG_PRESENTATION],
            paying=None,
            site_link=r'https://padlet.com/',
            description=r'Make beautiful tables, documents and web pages that are easy to read and fun to contribute.'
        )
        self._add_resource(
            icon='static/images/Powtoon.svg', name='Powtoon',
            tags=[_ExternalComponent.TAG_PRESENTATION, _ExternalComponent.TAG_SCREEN_RECORDER, _ExternalComponent.TAG_VIDEO],
            paying=True,
            site_link=r'https://www.powtoon.com/',
            description=r'Create, manage, and distribute all of your videos and visual communications.'
        )
        self._add_resource(
            icon='static/images/Prezi.svg', name='Prezi',
            tags=_ExternalComponent.TAG_PRESENTATION,
            paying=None,
            site_link=r'https://prezi.com/',
            description=r'Create interactive visuals that appear right next to you on screen as you present, for virtual presentations that engage, inspire, and educate.'
        )
        self._add_resource(
            icon='static/images/Screencast-O-Matic.svg', name='Screencast-O-Matic',
            tags=_ExternalComponent.TAG_SCREEN_RECORDER,
            paying=None,
            site_link=r'https://screencast-o-matic.com/home',
            description=r'Help you easily create, edit and communicate with videos and images. Simple and intuitive tools to share your ideas.'
        )
        self._add_resource(
            icon='static/images/Thinglink.svg', name='Thinglink',
            tags=_ExternalComponent.TAG_INFOGRAPHICS,
            paying=True,
            site_link=r'https://www.thinglink.com/',
            description=u'Create unique experiences with interactive images, videos & 360° media.'
        )
        self._add_resource(
            icon='static/images/Typeform.svg', name='Typeform',
            tags=_ExternalComponent.TAG_POLL,
            paying=True,
            site_link=r'https://www.typeform.com/',
            description=r'Create forms and surveys that people enjoy answering.'
        )
        self._add_resource(
            icon='static/images/Vimeo.svg', name='Vimeo',
            tags=_ExternalComponent.TAG_VIDEO,
            paying=None,
            site_link=r'https://vimeo.com/',
            description=r'Simple tools for you and your team to create, manage and share high-quality videos.'
        )

    def _add_resource(self, *args, **kwargs):
        """Add new External Web Content Configuration to vector"""
        # append get method obj. of xblock instance method
        kwargs['get_externality_handler'] = self.get_externality_handler

        external_component = _ExternalComponent(*args, **kwargs)
        self._listed_tags.update(external_component.get_tags_set())
        self._resources.append(external_component)

    def __iter__(self):
        """Return an iterable object"""
        return iter(self._resources)

    @property
    def listed_tags(self):
        """Return supported tags which were appended in method def __init__()
        """
        return [tag for tag in _ExternalComponent.ALL_TAGS if tag in self._listed_tags]

    @classmethod
    def assign_externality_handle(cls, obj):
        """Assign instance of external web content xblock to a class member

            @param obj:     instance of external web content xblock
            @type obj:      ExternalContentXBlock
            @return:        instance of xblock
            @rtype:         ExternalContentXBlock
        """
        if not cls._external_xblock_singleton:
            cls._external_xblock_singleton = obj

        return cls._external_xblock_singleton

    def get_externality_handler(self):
        """Return instance of external web content xblock"""
        if not SupportedExternalResources._external_xblock_singleton:
            raise ValueError('Invalid `SupportedExternalResources._external_xblock_singleton`. (None)')

        return SupportedExternalResources._external_xblock_singleton


SUPPORTED_EXTERNAL_RESOURCES = SupportedExternalResources()
