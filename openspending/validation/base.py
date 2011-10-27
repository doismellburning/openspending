from colander import Mapping, MappingSchema

class PreservingMappingSchema(MappingSchema):
    @classmethod
    def schema_type(cls):
        return Mapping(unknown='preserve')
