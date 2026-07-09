#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完全独立的脚本：解析 EVE Online brackets 相关的 static 文件并输出 JSON
不依赖任何第三方库，只使用 Python 标准库
Python 3 版本
"""

import sys
import os
import json
import struct
import ctypes
import pickle as cPickle  # Python 3: pickle (was cPickle in Python 2)
import array
import collections
import re
from contextlib import contextmanager
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.http_client import get

# ============================================================================
# 基础结构体定义
# ============================================================================

uint64 = struct.Struct('Q')
uint32 = struct.Struct('I')
int32 = struct.Struct('i')
keyedOffsetData = struct.Struct('ii')
keyedOffsetDataWithSize = struct.Struct('iii')
byte = struct.Struct('B')
cfloat = struct.Struct('f')
cdouble = struct.Struct('d')
vector2_float = struct.Struct('ff')
vector2_double = struct.Struct('dd')
vector3_float = struct.Struct('fff')
vector3_double = struct.Struct('ddd')
vector4_float = struct.Struct('ffff')
vector4_double = struct.Struct('dddd')


# ============================================================================
# 路径对象
# ============================================================================

class FsdDataPathObject(object):
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent

    def __str__(self):
        if self.parent is not None:
            return self.parent.__str__() + self.name
        else:
            return self.name


# ============================================================================
# Telemetry 上下文（简化版，不依赖 blue）
# ============================================================================

@contextmanager
def TelemetryContext(name):
    yield


# ============================================================================
# 辅助函数
# ============================================================================

def sizeof_fmt(num):
    for x in [' bytes', ' KB', ' MB', ' GB']:
        if num < 1024.0 and num > -1024.0:
            return '%3.1f%s' % (num, x)
        num /= 1024.0
    return '%3.1f%s' % (num, ' TB')


def readIntFromBinaryStringAtOffset(binaryString, offsetToValue):
    return uint32.unpack_from(binaryString, offsetToValue)[0]


def readIntFromFileAtOffset(fileObject, offsetToValue):
    fileObject.seek(offsetToValue)
    return uint32.unpack_from(fileObject.read(4), 0)[0]


def readBinaryDataFromFileAtOffset(fileObject, offsetToData, sizeOfData):
    fileObject.seek(offsetToData)
    return fileObject.read(sizeOfData)


def GetLargeEnoughUnsignedTypeForMaxValue(i):
    if i <= 255:
        return ctypes.c_ubyte
    elif i <= 65536:
        return ctypes.c_uint16
    else:
        return ctypes.c_uint32


# ============================================================================
# 数据类型加载器
# ============================================================================

class VectorLoader(object):
    def __init__(self, data, offset, schema, path, extraState):
        self.schema = schema
        single_precision = schema.get('precision', 'single') == 'single'
        schemaType = schema['type']
        if schemaType == 'vector4':
            t = vector4_float if single_precision else vector4_double
        elif schemaType == 'vector3':
            t = vector3_float if single_precision else vector3_double
        else:
            t = vector2_float if single_precision else vector2_double
        self.data = t.unpack_from(data, offset)

    def __getitem__(self, key):
        if 'aliases' in self.schema and key in self.schema['aliases']:
            return self.data[self.schema['aliases'][key]]
        return self.data[key]

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except (IndexError, KeyError) as e:
            raise AttributeError(str(e))


def Vector4FromBinaryString(data, offset, schema, path, extraState):
    if 'aliases' in schema:
        return VectorLoader(data, offset, schema, path, extraState)
    elif schema.get('precision', 'single') == 'double':
        return vector4_double.unpack_from(data, offset)
    else:
        return vector4_float.unpack_from(data, offset)


def Vector3FromBinaryString(data, offset, schema, path, extraState):
    if 'aliases' in schema:
        return VectorLoader(data, offset, schema, path, extraState)
    elif schema.get('precision', 'single') == 'double':
        return vector3_double.unpack_from(data, offset)
    else:
        return vector3_float.unpack_from(data, offset)


def Vector2FromBinaryString(data, offset, schema, path, extraState):
    if 'aliases' in schema:
        return VectorLoader(data, offset, schema, path, extraState)
    elif schema.get('precision', 'single') == 'double':
        return vector2_double.unpack_from(data, offset)
    else:
        return vector2_float.unpack_from(data, offset)


def StringFromBinaryString(data, offset, schema, path, extraState):
    count = uint32.unpack_from(data, offset)[0]
    result = struct.unpack_from(str(count) + 's', data, offset + 4)[0]
    # Python 3: decode bytes to string
    if isinstance(result, bytes):
        return result.decode('utf-8', errors='ignore')
    return result


def UnicodeStringFromBinaryString(data, offset, schema, path, extraState):
    nonUnicodeString = StringFromBinaryString(data, offset, schema, path, extraState)
    # StringFromBinaryString 已经返回字符串，这里直接返回
    if isinstance(nonUnicodeString, bytes):
        return nonUnicodeString.decode('utf-8', errors='ignore')
    return nonUnicodeString


def EnumFromBinaryString(data, offset, schema, path, extraState):
    enumType = GetLargeEnoughUnsignedTypeForMaxValue(schema['maxEnumValue'])
    dataValue = ctypes.cast(ctypes.byref(data, offset), ctypes.POINTER(enumType)).contents.value
    if schema.get('readEnumValue', False):
        return dataValue
    for k, v in schema['values'].items():  # Python 3: items() instead of iteritems()
        if v == dataValue:
            return k


def BoolFromBinaryString(data, offset, schema, path, extraState):
    return byte.unpack(data[offset])[0] == 255


def IntFromBinaryString(data, offset, schema, path, extraState):
    if 'min' in schema and schema['min'] >= 0 or 'exclusiveMin' in schema and schema['exclusiveMin'] >= -1:
        return uint32.unpack_from(data, offset)[0]
    else:
        return int32.unpack_from(data, offset)[0]


def FloatFromBinaryString(data, offset, schema, path, extraState):
    if schema.get('precision', 'single') == 'double':
        return cdouble.unpack_from(data, offset)[0]
    else:
        return cfloat.unpack_from(data, offset)[0]


def UnionFromBinaryString(data, offset, schema, path, extraState):
    typeIndex = uint32.unpack_from(data, offset)[0]
    return extraState.RepresentSchemaNode(data, offset + 4, path, schema['optionTypes'][typeIndex])


# ============================================================================
# 列表加载器
# ============================================================================

class FixedSizeListIterator(object):
    def __init__(self, data, offset, itemSchema, itemCount, path, itemSize, extraState):
        self.data = data
        self.offset = offset
        self.itemSchema = itemSchema
        self.count = itemCount
        self.itemSize = itemSize
        self.index = -1
        self.__path__ = path
        self.__extraState__ = extraState

    def __iter__(self):
        return self

    def __next__(self):  # Python 3: __next__() instead of next()
        self.index += 1
        if self.index == self.count:
            raise StopIteration()
        return self.__extraState__.RepresentSchemaNode(
            self.data, self.offset + self.itemSize * self.index,
            FsdDataPathObject('[%s]' % str(self.index), parent=self.__path__),
            self.itemSchema
        )

    def next(self):  # Python 2 compatibility
        return self.__next__()


class FixedSizeListRepresentation(object):
    def __init__(self, data, offset, itemSchema, path, extraState, knownLength=None):
        self.data = data
        self.offset = offset
        self.itemSchema = itemSchema
        self.__extraState__ = extraState
        self.__path__ = path
        if knownLength is None:
            self.count = uint32.unpack_from(data, offset)[0]
            self.fixedLength = False
        else:
            self.count = knownLength
            self.fixedLength = True
        self.itemSize = itemSchema['size']

    def __iter__(self):
        countOffset = 0 if self.fixedLength else 4
        return FixedSizeListIterator(
            self.data, self.offset + countOffset, self.itemSchema,
            self.count, self.__path__, self.itemSize, self.__extraState__
        )

    def __len__(self):
        return self.count

    def __getitem__(self, key):
        if type(key) not in (int,):  # Python 3: only int (long merged into int)
            raise TypeError('Invalid key type')
        if key < 0 or key >= self.count:
            raise IndexError('Invalid item index %i for list of length %i' % (key, self.count))
        countOffset = 0 if self.fixedLength else 4
        totalOffset = self.offset + countOffset + self.itemSize * key
        return self.__extraState__.RepresentSchemaNode(
            self.data, totalOffset,
            FsdDataPathObject('[%s]' % str(key), parent=self.__path__),
            self.itemSchema
        )


class VariableSizedListRepresentation(object):
    def __init__(self, data, offset, itemSchema, path, extraState, knownLength=None):
        self.data = data
        self.offset = offset
        self.itemSchema = itemSchema
        self.__extraState__ = extraState
        self.__path__ = path
        if knownLength is None:
            self.count = uint32.unpack_from(data, offset)[0]
            self.fixedLength = False
        else:
            self.count = knownLength
            self.fixedLength = True

    def __len__(self):
        return self.count

    def __getitem__(self, key):
        if type(key) not in (int,):  # Python 3: only int (long merged into int)
            raise TypeError('Invalid key type')
        if key < 0 or key >= self.count:
            raise IndexError('Invalid item index %i for list of length %i' % (key, self.count))
        countOffset = 0 if self.fixedLength else 4
        dataOffsetFromObjectStart = uint32.unpack_from(
            self.data, self.offset + countOffset + 4 * key
        )[0]
        return self.__extraState__.RepresentSchemaNode(
            self.data, self.offset + dataOffsetFromObjectStart,
            FsdDataPathObject('[%s]' % str(key), parent=self.__path__),
            self.itemSchema
        )


def ListFromBinaryString(data, offset, schema, path, extraState, knownLength=None):
    knownLength = schema.get('length', knownLength)
    if 'fixedItemSize' in schema:
        listLikeObject = FixedSizeListRepresentation(
            data, offset, schema['itemTypes'], path, extraState, knownLength
        )
    else:
        listLikeObject = VariableSizedListRepresentation(
            data, offset, schema['itemTypes'], path, extraState, knownLength
        )
    return list(listLikeObject)


# ============================================================================
# 字典加载器
# ============================================================================

class StandardFSDOptimizedDictFooter(object):
    def __init__(self, data, schema):
        self.data = data
        if 'size' in schema['keyFooter']['itemTypes']['attributes']:
            self.unpacker = keyedOffsetDataWithSize
            self.offsetDataHasSizeAttribute = True
        else:
            self.unpacker = keyedOffsetData
            self.offsetDataHasSizeAttribute = False
        self.listItemSize = self.unpacker.size
        self.startingOffset = 4
        self.size = readIntFromBinaryStringAtOffset(data, 0)

    def Get(self, key):
        minIndex = 0
        maxIndex = self.size - 1
        while 1:
            if maxIndex < minIndex:
                return None
            meanIndex = (minIndex + maxIndex) / 2
            currentObjectOffset = meanIndex * self.listItemSize + self.startingOffset
            currentKey, offset, size = self.__unpackFromOffset__(currentObjectOffset)
            if currentKey < key:
                minIndex = meanIndex + 1
            elif currentKey > key:
                maxIndex = meanIndex - 1
            else:
                return (offset, size)

    def __len__(self):
        return self.size

    def __unpackFromOffset__(self, currentObjectOffset):
        if self.offsetDataHasSizeAttribute:
            currentKey, offset, size = self.unpacker.unpack_from(self.data, currentObjectOffset)
        else:
            currentKey, offset = self.unpacker.unpack_from(self.data, currentObjectOffset)
            size = 0
        return (currentKey, offset, size)

    def items(self):  # Python 3: items() instead of iteritems()
        for i in range(0, self.size):
            currentObjectOffset = i * self.listItemSize + self.startingOffset
            currentKey, offset, size = self.__unpackFromOffset__(currentObjectOffset)
            yield (currentKey, (offset, size))

    def iteritems(self):  # Keep for backward compatibility
        return self.items()


class StandardFSDDictFooter(object):
    def __init__(self, data, offset, schema, path, extraState):
        self.footerData = extraState.factories['list'](data, offset, schema, path, extraState)
        self.size = len(self.footerData)

    def Get(self, key):
        minIndex = 0
        maxIndex = self.size - 1
        while 1:
            if maxIndex < minIndex:
                return None
            meanIndex = (minIndex + maxIndex) / 2
            item = self.footerData[meanIndex]
            if item['key'] < key:
                minIndex = meanIndex + 1
            elif item['key'] > key:
                maxIndex = meanIndex - 1
            else:
                return (item['offset'], getattr(item, 'size', 0))

    def __len__(self):
        return self.size

    def items(self):  # Python 3: items() instead of iteritems()
        for item in self.footerData:
            yield (item.key, (item.offset, getattr(item, 'size', 0)))

    def iteritems(self):  # Keep for backward compatibility
        return self.items()


def CreatePythonDictOffset(schema, binaryFooterData, path, extraState):
    useOptimizedPythonOffsetStructure = schema['keyTypes']['type'] == 'int'
    buff = ctypes.create_string_buffer(binaryFooterData, len(binaryFooterData))
    if useOptimizedPythonOffsetStructure:
        return StandardFSDOptimizedDictFooter(buff, schema)
    else:
        return StandardFSDDictFooter(buff, 0, schema['keyFooter'], FsdDataPathObject('<keyFooter>', parent=path),
                                     extraState)


def CreateDictFooter(schema, binaryFooterData, path, extraState):
    return CreatePythonDictOffset(schema, binaryFooterData, path, extraState)


class DictLoader(object):
    def __init__(self, data, offset, schema, path, extraState):
        self.data = data
        self.offset = offset
        self.schema = schema
        self.sizeOfData = readIntFromBinaryStringAtOffset(self.data, self.offset)
        offsetToSizeOfFooter = self.offset + 4 + self.sizeOfData - 4
        self.sizeOfFooter = readIntFromBinaryStringAtOffset(self.data, offsetToSizeOfFooter)
        self.__extraState__ = extraState
        self.__path__ = path
        self.index = {}
        offsetToStartOfFooter = self.offset + self.sizeOfData - self.sizeOfFooter
        footerData = data[offsetToStartOfFooter:offsetToStartOfFooter + self.sizeOfFooter]
        self.footer = CreatePythonDictOffset(schema, footerData, path, extraState)

    def __getitem__(self, key):
        v = self._Search(key)
        if v is None:
            raise KeyError('key (%s) not found in %s' % (str(key), self.__path__))
        return self.__GetItemFromOffset__(key, v[0])

    def __GetItemFromOffset__(self, key, offset):
        return self.__extraState__.RepresentSchemaNode(
            self.data, self.offset + 4 + offset,
            FsdDataPathObject('[%s]' % str(key), parent=self.__path__),
            self.schema['valueTypes']
        )

    def __len__(self):
        return len(self.footer)

    def __contains__(self, item):
        try:
            x = self._Search(item)
            return x is not None
        except TypeError:
            return False

    def _Search(self, key):
        if key not in self.index:
            searchResult = self.footer.Get(key)
            if searchResult is not None:
                self.index[key] = searchResult
            else:
                self.index[key] = None
            return searchResult
        return self.index[key]

    def Get(self, key):
        return self.__getitem__(key)

    def get(self, key, default):
        v = self._Search(key)
        if v is not None:
            return self.__GetItemFromOffset__(key, v[0])
        else:
            return default

    def GetIfExists(self, key):
        return self.get(key, None)

    def values(self):  # Python 3: values() instead of itervalues()
        for key, (offset, size) in self.footer.items():
            yield self.__GetItemFromOffset__(key, offset)

    def itervalues(self):  # Keep for backward compatibility
        return self.values()

    def keys(self):  # Python 3: keys() returns iterator
        for key, _ in self.footer.items():
            yield key

    def iterkeys(self):  # Keep for backward compatibility
        return self.keys()

    def items(self):  # Python 3: items() instead of iteritems()
        for key, (offset, size) in self.footer.items():
            yield (key, self.__GetItemFromOffset__(key, offset))

    def iteritems(self):  # Keep for backward compatibility
        return self.items()

    def __iter__(self):
        return self.keys()


# ============================================================================
# 对象加载器
# ============================================================================

class ObjectLoader(object):
    def __init__(self, data, offset, schema, path, extraState):
        self.__data__ = data
        self.__offset__ = offset
        self.__schema__ = schema
        self.__extraState__ = extraState
        self.__path__ = path
        self.__hasOptionalAttributes__ = False
        self.__offsetAttributesOffsetLookupTable__ = {}
        if 'size' not in schema:
            __offsetAttributes__ = schema.get('attributesWithVariableOffsets', [])[:]
            if self.__schema__.get('optionalValueLookups'):
                self.__hasOptionalAttributes__ = True
                optionalAttributesField = uint64.unpack_from(data, offset + schema['endOfFixedSizeData'])[0]
                for attr, i in self.__schema__['optionalValueLookups'].items():  # Python 3: items()
                    if not optionalAttributesField & i:
                        if attr in __offsetAttributes__:
                            __offsetAttributes__.remove(attr)

            offsetAttributeArrayStart = offset + schema.get('endOfFixedSizeData', 0) + 8
            offsetAttributeOffsetsType = ctypes.c_uint32 * len(__offsetAttributes__)
            self.__variableDataOffsetBase__ = offsetAttributeArrayStart + ctypes.sizeof(offsetAttributeOffsetsType)
            offsetData = data[offsetAttributeArrayStart:offsetAttributeArrayStart + ctypes.sizeof(
                offsetAttributeOffsetsType)]
            offsetTable = array.array('I', offsetData).tolist()
            for k, v in zip(__offsetAttributes__, offsetTable):
                self.__offsetAttributesOffsetLookupTable__[k] = v

    def __repr__(self):
        return '<FSD Object: %s >' % self.__path__

    def __getitem__(self, key):
        if key not in self.__schema__['attributes']:
            raise KeyError("Object: %s - Attribute '%s' is not in the schema" % (self.__path__, key))
        attributeSchema = self.__schema__['attributes'][key]
        if key in self.__schema__['constantAttributeOffsets']:
            return self.__extraState__.RepresentSchemaNode(
                self.__data__, self.__offset__ + self.__schema__['constantAttributeOffsets'][key],
                FsdDataPathObject('.%s' % str(key), parent=self.__path__),
                attributeSchema
            )
        else:
            if key not in self.__offsetAttributesOffsetLookupTable__:
                if 'default' in attributeSchema:
                    return attributeSchema['default']
                raise KeyError("Object: %s - Attribute '%s' is not present" % (self.__path__, key))
            return self.__extraState__.RepresentSchemaNode(
                self.__data__, self.__variableDataOffsetBase__ + self.__offsetAttributesOffsetLookupTable__[key],
                FsdDataPathObject('.%s' % str(key), parent=self.__path__),
                attributeSchema
            )

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except KeyError as e:
            raise AttributeError(str(e))


# ============================================================================
# 加载器状态和工厂
# ============================================================================

defaultLoaderFactories = {
    'float': FloatFromBinaryString,
    'vector4': Vector4FromBinaryString,
    'vector3': Vector3FromBinaryString,
    'vector2': Vector2FromBinaryString,
    'string': StringFromBinaryString,
    'resPath': StringFromBinaryString,
    'enum': EnumFromBinaryString,
    'bool': BoolFromBinaryString,
    'int': IntFromBinaryString,
    'typeID': IntFromBinaryString,
    'localizationID': IntFromBinaryString,
    'union': UnionFromBinaryString,
    'list': ListFromBinaryString,
    'object': ObjectLoader,
    'dict': DictLoader,
    'unicode': UnicodeStringFromBinaryString
}


class LoaderState(object):
    def __init__(self, factories, logger=None, cfgObject=None):
        self.factories = factories

    def RepresentSchemaNode(self, data, offset, path, schemaNode):
        schemaType = schemaNode.get('type')
        if schemaType in self.factories:
            return self.factories[schemaType](data, offset, schemaNode, path, self)
        raise NotImplementedError("Unknown type not supported in binary loader '%s'" % str(schemaType))

    def FormatSize(self, size):
        return sizeof_fmt(size)


def RepresentSchemaNode(data, offset, schemaNode, path, extraState=None):
    schemaType = schemaNode.get('type')
    if extraState is None:
        extraState = LoaderState(defaultLoaderFactories, None)
    if schemaType in extraState.factories:
        return extraState.factories[schemaType](data, offset, schemaNode, path, extraState)
    raise NotImplementedError("Unknown type not supported in binary loader '%s'" % str(schemaType))


# ============================================================================
# 主要加载函数
# ============================================================================

def GetEmbeddedSchemaAndSizeFromFile(fileObject):
    schemaSize = uint32.unpack(fileObject.read(4))[0]
    pickledSchema = fileObject.read(schemaSize)
    return (cPickle.loads(pickledSchema), schemaSize)


def LoadFromString(dataString, optimizedSchema=None, path=None, extraState=None):
    if path is None:
        path = FsdDataPathObject('<string input>')
    offsetToData = 0
    if optimizedSchema is None:
        schemaSize = uint32.unpack_from(dataString, 0)[0]
        optimizedSchema = cPickle.loads(dataString[4:schemaSize + 4])
        offsetToData = schemaSize + 4
    dataBuffer = ctypes.create_string_buffer(dataString, len(dataString))
    return RepresentSchemaNode(dataBuffer, offsetToData, optimizedSchema, path, extraState)


def LoadFSDDataInPython(dataResPath, schemaResPath=None, optimize=None, cacheSize=100, dataBytes=None):
    """
    加载 FSD 数据文件
    
    Args:
        dataResPath: 文件路径（如果 dataBytes 为 None）
        schemaResPath: schema 文件路径（未使用）
        optimize: 优化选项（未使用）
        cacheSize: 缓存大小（未使用）
        dataBytes: 可选的二进制数据（如果提供，则直接使用而不从文件读取）
    """
    schema = None
    if dataBytes is not None:
        # 从内存数据加载
        if schema is None:
            schemaSize = uint32.unpack_from(dataBytes, 0)[0]
            peekSchema = cPickle.loads(dataBytes[4:schemaSize + 4])
        else:
            peekSchema = schema
        if peekSchema['type'] == 'dict' and peekSchema.get('buildIndex', False):
            pass
        print('Loading FSD data from memory. %s' % sizeof_fmt(len(dataBytes)))
        return LoadFromString(dataBytes, schema, path=FsdDataPathObject('<memory data>'))
    else:
        # 从文件加载（原有逻辑）
        dataFile = open(dataResPath, 'rb')
        if schema is None:
            peekSchema, size = GetEmbeddedSchemaAndSizeFromFile(dataFile)
            dataFile.seek(0)
        else:
            peekSchema = schema
        if peekSchema['type'] == 'dict' and peekSchema.get('buildIndex', False):
            # 对于索引字典，我们需要使用 IndexLoader，但为了简化，我们直接加载全部
            # 实际使用中，如果文件很大，可能需要实现 IndexLoader
            pass
        s = dataFile.read()
        print('Loading FSD data file %s into memory. %s' % (dataResPath, sizeof_fmt(len(s))))
        dataFile.close()
        return LoadFromString(s, schema, path=FsdDataPathObject('<file %s>' % dataResPath))


# ============================================================================
# FSD 对象转字典
# ============================================================================

def fsd_to_dict(obj, visited=None):
    """递归将 FSD 对象转换为 Python 字典"""
    if visited is None:
        visited = set()

    obj_id = id(obj)
    if obj_id in visited:
        return "<circular reference>"
    visited.add(obj_id)

    try:
        # 处理字典类型（DictLoader）
        if hasattr(obj, 'items') or hasattr(obj, 'iteritems'):
            result = {}
            try:
                # Python 3: prefer items(), fallback to iteritems() for compatibility
                items = obj.items() if hasattr(obj, 'items') and callable(
                    getattr(obj, 'items', None)) else obj.iteritems()
                for key, value in items:
                    # 处理 key：如果是 bytes，转换为字符串
                    if isinstance(key, bytes):
                        key = key.decode('utf-8', errors='ignore')
                    elif not isinstance(key, (int, str)):
                        key = str(key)
                    result[str(key)] = fsd_to_dict(value, visited)
            except (TypeError, AttributeError):
                pass
            visited.remove(obj_id)
            return result

        # 处理列表类型
        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
            try:
                result = [fsd_to_dict(item, visited) for item in obj]
                visited.remove(obj_id)
                return result
            except (TypeError, AttributeError):
                pass

        # 处理 ObjectLoader 对象
        if hasattr(obj, '__schema__') or (hasattr(obj, '__getitem__') and not isinstance(obj, dict)):
            result = {}
            try:
                if hasattr(obj, '__schema__'):
                    schema = obj.__schema__
                    if isinstance(schema, dict):
                        schema_attrs = schema.get('attributes', {})
                        for attr_name in schema_attrs.keys():
                            try:
                                value = obj[attr_name]
                                result[attr_name] = fsd_to_dict(value, visited)
                            except (KeyError, AttributeError, TypeError):
                                attr_schema = schema_attrs.get(attr_name, {})
                                if 'default' in attr_schema:
                                    result[attr_name] = fsd_to_dict(attr_schema['default'], visited)
            except (AttributeError, TypeError):
                pass
            visited.remove(obj_id)
            return result if result else str(obj)

        # 处理基本类型
        if isinstance(obj, (int, float, bool, type(None))):  # Python 3: no long type
            visited.remove(obj_id)
            return obj

        if isinstance(obj, (str, bytes)):  # Python 3: str is unicode, bytes is binary
            visited.remove(obj_id)
            if isinstance(obj, bytes):
                # 尝试解码为字符串
                try:
                    return obj.decode('utf-8', errors='ignore')
                except:
                    return str(obj)
            # 如果已经是字符串，检查是否有 b'...' 这样的表示
            s = str(obj)
            # 如果字符串看起来像是 bytes 的 repr，尝试提取实际内容
            if s.startswith("b'") and s.endswith("'") or s.startswith('b"') and s.endswith('"'):
                # 提取引号内的内容
                content = s[2:-1]
                # 处理转义字符
                try:
                    return content.encode('latin-1').decode('unicode_escape').encode('latin-1').decode('utf-8',
                                                                                                       errors='ignore')
                except:
                    return content
            return s

        # 处理元组（转换为列表以便 JSON 序列化）
        if isinstance(obj, tuple):
            result = [fsd_to_dict(item, visited) for item in obj]
            visited.remove(obj_id)
            return result

        visited.remove(obj_id)
        return str(obj)

    except Exception as e:
        visited.discard(obj_id)
        return "<error: %s>" % str(e)


# ============================================================================
# 在线下载功能
# ============================================================================

def _get_build_info():
    """获取EVE客户端的最新构建信息"""
    try:
        print("[+] 获取EVE客户端构建信息...")
        url = "https://binaries.eveonline.com/eveclient_TQ.json"
        response = get(url, timeout=30, verify=False)
        build_info = response.json()
        print("[+] 当前构建版本: %s" % build_info.get('build'))
        return build_info
    except Exception as e:
        print("[x] 获取构建信息失败: %s" % str(e))
        return None


def _get_resfile_index_content():
    """从在线服务器获取resfileindex.txt内容"""
    build_info = _get_build_info()
    if not build_info:
        return None
    
    build_number = build_info.get('build')
    if not build_number:
        return None
    
    try:
        print("[+] 从在线服务器获取resfileindex...")
        
        # 下载 installer 文件
        installer_url = "https://binaries.eveonline.com/eveonline_%s.txt" % build_number
        response = get(installer_url, timeout=30, verify=False)
        installer_content = response.text
        
        # 解析installer文件找到resfileindex
        resfileindex_path = None
        for line in installer_content.split('\n'):
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) >= 2 and parts[0] == "app:/resfileindex.txt":
                resfileindex_path = parts[1]
                break
        
        if not resfileindex_path:
            print("[x] 在installer文件中未找到resfileindex路径")
            return None
        
        # 下载resfileindex文件内容
        resfile_url = "https://binaries.eveonline.com/%s" % resfileindex_path
        response = get(resfile_url, timeout=60, verify=False)
        resfile_content = response.text
        
        print("[+] resfileindex获取完成")
        return resfile_content
        
    except Exception as e:
        print("[x] 获取resfileindex失败: %s" % str(e))
        import traceback
        traceback.print_exc()
        return None


def _parse_brackets_files_from_resfileindex(resfile_content):
    """从resfileindex内容中解析brackets文件的路径信息"""
    brackets_files = {
        'brackets': 'res:/staticdata/brackets.static',
        'bracketsByCategory': 'res:/staticdata/bracketsbycategory.static',
        'bracketsByGroup': 'res:/staticdata/bracketsbygroup.static',
        'bracketsByType': 'res:/staticdata/bracketsbytype.static'
    }
    
    result = {}
    
    for name, res_path in brackets_files.items():
        # 在resfileindex中查找对应的行
        pattern = re.escape(res_path) + r',([^,]+),([^,]+)'
        match = re.search(pattern, resfile_content)
        if match:
            file_path = match.group(1)
            file_hash = match.group(2)
            result[name] = {
                'res_path': res_path,
                'file_path': file_path,
                'hash': file_hash
            }
            print("[+] 找到 %s: %s" % (name, file_path))
        else:
            print("[x] 在resfileindex中未找到 %s" % name)
    
    return result


def _download_static_file(file_path):
    """从EVE资源服务器下载static文件"""
    try:
        download_url = "https://resources.eveonline.com/%s" % file_path
        print("[+] 开始下载: %s" % download_url)
        
        response = get(download_url, timeout=60, verify=False)
        file_data = response.content
        
        print("[+] 下载完成，大小: %s" % sizeof_fmt(len(file_data)))
        return file_data
        
    except Exception as e:
        print("[x] 下载文件失败 %s: %s" % (file_path, str(e)))
        import traceback
        traceback.print_exc()
        return None


def download_and_parse_brackets_files(use_cache=True):
    """从在线服务器下载并解析brackets文件"""
    print("\n" + "=" * 60)
    print("从在线服务器下载 brackets 文件...")
    print("=" * 60)
    
    # 获取resfileindex内容
    resfile_content = _get_resfile_index_content()
    if not resfile_content:
        return {"error": "无法获取resfileindex"}
    
    # 解析brackets文件路径
    brackets_info = _parse_brackets_files_from_resfileindex(resfile_content)
    if not brackets_info:
        return {"error": "在resfileindex中未找到brackets文件"}
    
    result = {}
    
    # 创建临时目录用于缓存（可选）
    cache_dir = None
    if use_cache:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(script_dir, 'raw')
        os.makedirs(cache_dir, exist_ok=True)
    
    print("\n开始下载和解析 brackets 文件...")
    print("=" * 60)
    
    for name, file_info in brackets_info.items():
        print("\n正在处理: %s" % name)
        file_path = file_info['file_path']
        file_hash = file_info['hash']
        
        # 检查缓存
        file_data = None
        if use_cache and cache_dir:
            cache_file = os.path.join(cache_dir, os.path.basename(file_path))
            if os.path.exists(cache_file):
                print("[+] 使用缓存文件: %s" % cache_file)
                try:
                    with open(cache_file, 'rb') as f:
                        file_data = f.read()
                except Exception as e:
                    print("[!] 读取缓存文件失败: %s" % str(e))
        
        # 如果缓存不存在，则下载
        if file_data is None:
            file_data = _download_static_file(file_path)
            if file_data is None:
                result[name] = {"error": "下载失败: %s" % file_path}
                continue
            
            # 保存到缓存
            if use_cache and cache_dir:
                cache_file = os.path.join(cache_dir, os.path.basename(file_path))
                try:
                    with open(cache_file, 'wb') as f:
                        f.write(file_data)
                    print("[+] 已保存到缓存: %s" % cache_file)
                except Exception as e:
                    print("[!] 保存缓存失败: %s" % str(e))
        
        # 解析文件
        try:
            print("[+] 正在解析 %s..." % name)
            data = LoadFSDDataInPython(None, dataBytes=file_data)
            print("[+] 正在转换为字典格式...")
            dict_data = fsd_to_dict(data)
            
            if isinstance(dict_data, dict):
                print("[+] 条目数量: %d" % len(dict_data))
                if dict_data:
                    sample_keys = list(dict_data.keys())[:5]
                    print("[+] 示例键: %s" % sample_keys)
            
            result[name] = dict_data
            print("[+] ✓ %s 解析成功" % name)
            
        except Exception as e:
            error_msg = "[x] ✗ %s 解析失败: %s" % (name, str(e))
            print(error_msg)
            import traceback
            traceback.print_exc()
            result[name] = {"error": str(e)}
    
    return result


# ============================================================================
# 主程序
# ============================================================================

def parse_brackets_files(staticdata_dir):
    """解析四个 brackets 相关的 static 文件

    Args:
        staticdata_dir: 输入文件目录路径
    """
    if not os.path.exists(staticdata_dir):
        print("错误: 找不到输入目录！")
        print("请确保目录存在于: %s" % staticdata_dir)
        return {"error": "找不到输入目录"}

    print("使用输入目录: %s" % staticdata_dir)

    file_names = {
        'bracketsByCategory': 'bracketsbycategory.static',
        'bracketsByGroup': 'bracketsbygroup.static',
        'bracketsByType': 'bracketsbytype.static',
        'brackets': 'brackets.static'
    }

    result = {}

    print("\n开始解析 brackets 文件...")
    print("=" * 60)

    for name, file_name in file_names.items():
        file_path = os.path.join(staticdata_dir, file_name)
        print("\n正在解析: %s" % name)
        print("文件路径: %s" % file_path)

        if not os.path.exists(file_path):
            print("✗ 文件不存在: %s" % file_path)
            result[name] = {"error": "文件不存在: %s" % file_path}
            continue

        try:
            data = LoadFSDDataInPython(file_path, optimize=False)
            print("正在转换为字典格式...")
            dict_data = fsd_to_dict(data)

            if isinstance(dict_data, dict):
                print("条目数量: %d" % len(dict_data))
                if dict_data:
                    sample_keys = list(dict_data.keys())[:5]
                    print("示例键: %s" % sample_keys)

            result[name] = dict_data
            print("✓ 解析成功")

        except Exception as e:
            error_msg = "✗ 解析失败: %s" % str(e)
            print(error_msg)
            import traceback
            traceback.print_exc()
            result[name] = {"error": str(e)}

    return result


def main():
    """主函数"""
    print("=" * 60)
    print("EVE Online Brackets Static 文件解析工具 (独立版)")
    print("=" * 60)

    try:
        # 优先尝试在线下载
        print("\n[+] 尝试从在线服务器下载文件...")
        all_data = download_and_parse_brackets_files(use_cache=True)
        
        # 如果在线下载失败，回退到本地文件
        # 检查是否有错误或结果为空
        has_error = False
        if isinstance(all_data, dict):
            if 'error' in all_data:
                has_error = True
            else:
                # 检查是否有任何文件解析失败
                for name, data in all_data.items():
                    if isinstance(data, dict) and 'error' in data:
                        has_error = True
                        break
        
        if has_error or not all_data:
            print("\n[!] 在线下载失败或部分失败，尝试使用本地文件...")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            staticdata_dir = os.path.join(script_dir, 'raw')
            
            if os.path.exists(staticdata_dir):
                local_data = parse_brackets_files(staticdata_dir)
                # 合并结果，优先使用在线下载的数据
                for name, data in local_data.items():
                    if name not in all_data or 'error' in all_data.get(name, {}):
                        all_data[name] = data
            else:
                print("[x] 本地目录不存在，且在线下载失败")
                if not all_data:
                    all_data = {"error": "无法从在线服务器下载，且本地目录不存在"}

        # 检查是否有任何错误，如果有错误则不生成文件
        print("\n" + "=" * 60)
        print("检查数据完整性...")
        print("=" * 60)
        
        has_error = False
        required_fields = ['brackets', 'bracketsByType', 'bracketsByGroup', 'bracketsByCategory']
        
        # 检查顶层错误
        if 'error' in all_data:
            print("[x] 顶层错误: %s" % all_data.get('error'))
            has_error = True
        
        # 检查必需字段是否存在且有效
        for field in required_fields:
            if field not in all_data:
                print("[x] 缺少必需字段: %s" % field)
                has_error = True
            else:
                field_data = all_data[field]
                if not isinstance(field_data, dict):
                    print("[x] 字段 %s 不是有效的字典类型" % field)
                    has_error = True
                elif 'error' in field_data:
                    print("[x] 字段 %s 解析失败: %s" % (field, field_data.get('error')))
                    has_error = True
                elif len(field_data) == 0:
                    print("[x] 字段 %s 为空" % field)
                    has_error = True
        
        if has_error:
            print("\n[x] 数据解析存在错误，不生成 brackets_output.json 文件")
            print("[x] 请检查错误信息并修复后重试")
            return
        
        print("[+] 所有必需字段解析成功，数据完整性检查通过")
        
        print("\n" + "=" * 60)
        print("优化数据结构，合并 name 信息...")
        
        # 优化数据结构：将 brackets 中的 name 合并到其他结构中
        def enrich_with_bracket_name(mapping_dict, brackets_dict, mapping_name):
            """将 bracket ID 映射转换为包含 name 的对象"""
            if not isinstance(mapping_dict, dict):
                return mapping_dict
            
            optimized = {}
            for key, bracket_id in mapping_dict.items():
                bracket_id_str = str(bracket_id)
                if bracket_id_str in brackets_dict and isinstance(brackets_dict[bracket_id_str], dict):
                    optimized[key] = {
                        'bracketId': bracket_id,
                        'name': brackets_dict[bracket_id_str].get('name', '')
                    }
                else:
                    optimized[key] = {
                        'bracketId': bracket_id,
                        'name': ''
                    }
            print("[+] 已优化 %s: %d 个条目" % (mapping_name, len(optimized)))
            return optimized
        
        if 'brackets' in all_data and isinstance(all_data['brackets'], dict):
            brackets = all_data['brackets']
            
            # 处理 bracketsByType
            if 'bracketsByType' in all_data:
                all_data['bracketsByType'] = enrich_with_bracket_name(
                    all_data['bracketsByType'], brackets, 'bracketsByType'
                )
            
            # 处理 bracketsByGroup
            if 'bracketsByGroup' in all_data:
                all_data['bracketsByGroup'] = enrich_with_bracket_name(
                    all_data['bracketsByGroup'], brackets, 'bracketsByGroup'
                )
            
            # 处理 bracketsByCategory
            if 'bracketsByCategory' in all_data:
                all_data['bracketsByCategory'] = enrich_with_bracket_name(
                    all_data['bracketsByCategory'], brackets, 'bracketsByCategory'
                )

        print("\n" + "=" * 60)
        print("生成 JSON 输出...")

        class FSDJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                # Python 3: no long type (merged into int)
                if isinstance(obj, (tuple, set, frozenset)):
                    return list(obj)
                if isinstance(obj, bytes):
                    return obj.decode('utf-8', errors='ignore')
                return super(FSDJSONEncoder, self).default(obj)

        # 使用脚本所在目录的绝对路径，确保文件生成在正确的位置
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(script_dir, 'brackets_output.json')
        # Python 3: open() supports encoding parameter
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False, cls=FSDJSONEncoder, default=str)

        print("✓ JSON 已保存到: %s" % output_file)

        print("\n" + "=" * 60)
        print("统计信息:")
        print("=" * 60)
        for name, data in all_data.items():
            if isinstance(data, dict) and 'error' not in data:
                print("%s: %d 个条目" % (name, len(data)))
            else:
                print("%s: 解析失败" % name)

        print("\n✓ 完成！")

    except Exception as e:
        print("\n✗ 发生错误: %s" % str(e))
        import traceback
        traceback.print_exc()
        print("[!] brackets_output.json 生成失败")
        return


if __name__ == '__main__':
    main()

