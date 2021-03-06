from flask import Blueprint, jsonify, request
from bson import ObjectId
from auth import raise_status, filter
import logging
import traceback
import requests

projects = Blueprint('projects', __name__)


@projects.route('/projects', methods=['POST'])
def project_create():
    from application.project_app import project_app
    from model import PROJECT
    requestObj = request.json
    try:
        requestObj['creator'] = ObjectId(requestObj['creator'])
        requestObj['tag'] = ObjectId(requestObj['tag'])
        git_list = requestObj['githuburl'].split('/')
        git_account = git_list[3] + '/'
        if '.git' in git_list[4]:
            repo = git_list[4][: -4] + '/'
        else:
            repo = git_list[4] + '/'
        url = 'https://raw.githubusercontent.com/' + git_account + repo + 'master/index.json'
        try:
            r = requests.get(url=url)
            labs = r.json()['labs']
        except Exception as e:
            logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
            return raise_status(400, '获取元数据失败')
        query_list = ['creator', 'title', 'description', 'requirement', 'timeConsume',
                      'material', 'reference', 'image', 'base', 'spec', 'tag']
        requestObj = filter(query_list=query_list, updateObj=requestObj)
        if project_app(requestObj={'title': requestObj['title']}).project_check():
            return raise_status(400, 'project标题重复')
        if not requestObj.get('base'):
            requestObj['base'] = None
        else:
            requestObj['base'] = ObjectId(requestObj['base'])
            try:
                PROJECT.objects.get({'_id': requestObj['base'], 'delete': False})
            except PROJECT.DoesNotExist:
                return raise_status(400, '无效的引用信息')
        try:
            project_model = project_app(requestObj=requestObj).project_create()
        except Exception as e:
            logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
            return raise_status(500, '后台异常')
        lab_list = []
        for lab in labs:
            index = str(labs.index(lab)) if labs.index(lab) >= 10 else '0' + str(labs.index(lab))
            key_list = list(lab.keys())
            value_list = list(lab.values())
            lab_list.append({
                'id': str(project_model._id) + index,
                'filename': key_list[0],
                'name': value_list[0]
            })
        try:
            project_app(requestObj={'_id': project_model._id}, updateObj={'labs': lab_list}).project_update_set()
        except Exception as e:
            logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
            return raise_status(500, '后台异常')
        if project_model.base is None:
            base = None
        else:
            if request.args.get('embed'):
                if project_model.base.base is None:
                    base_reference = None
                else:
                    base_reference = str(project_model.base.base._id)
                base = {
                    'id': str(project_model.base._id),
                    'creator': str(project_model.base.creator),
                    'description': project_model.base.description,
                    'title': project_model.base.title,
                    'requirement': project_model.base.requirement,
                    'material': project_model.base.material,
                    'timeConsume': project_model.base.timeConsume,
                    'tag': project_model.base.tag.name,
                    'reference': project_model.base.reference,
                    'labs': project_model.base.labs,
                    'image': project_model.base.image,
                    'base': base_reference,
                    'spec': project_model.base.spec,
                    'createdAt': project_model.base.createdAt,
                    'updatedAt': project_model.base.updatedAt
                }
            else:
                base = str(project_model.base._id)
        data = {
            'id': str(project_model._id),
            'creator': str(project_model.creator),
            'title': project_model.title,
            'description': project_model.description,
            'requirement': project_model.requirement,
            'material': project_model.material,
            'timeConsume': project_model.timeConsume,
            'tag': project_model.tag.name,
            'labs': lab_list,
            'reference': project_model.reference,
            'image': project_model.image,
            'base': base,
            'spec': project_model.spec,
            'createdAt': project_model.createdAt,
            'updatedAt': project_model.updatedAt
        }
    except Exception as e:
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return raise_status(500, '后台异常')
    return jsonify(data)


@projects.route('/projects', methods=['GET'])
def project_list():
    from application.project_app import project_app
    from model import PROJECT
    try:
        page = int(request.args.get('page', '1'))
        pageSize = int(request.args.get('pageSize', '20'))
        if request.args.get('id'):
            id_list = request.args['id'].replace('[', '').replace(']', '').replace(' ', ''). \
                replace("'", '').replace('"', '').split(',')
            ObjectId_list = []
            for i in id_list:
                ObjectId_list.append(ObjectId(i))
            model_list = list(PROJECT.objects.raw({'_id': {'$in': ObjectId_list}, 'delete': False}))
            project_dict = {}
            for project_model in model_list:
                if project_model.base is None:
                    base = None
                else:
                    base = str(project_model.base._id)
                project_dict[str(project_model._id)] = {
                    'id': str(project_model._id),
                    'creator': str(project_model.creator),
                    'description': project_model.description,
                    'title': project_model.title,
                    'requirement': project_model.requirement,
                    'labs': project_model.labs,
                    'tag': project_model.tag.name,
                    'material': project_model.material,
                    'reference': project_model.reference,
                    'timeConsume': project_model.timeConsume,
                    'image': project_model.image,
                    'base': base,
                    'spec': project_model.spec,
                    'createdAt': project_model.createdAt,
                    'updatedAt': project_model.updatedAt
                }
            return jsonify(project_dict)
        query = [ObjectId(x) for x in
                 request.args['tag'].replace('[', '').replace(']', '').replace('"', '').replace("'", '').replace(' ',
                                                                                                                 '').split(
                     ',')] if request.args.get('tag') else None
        querySet = {'tag': {'$in': query}} if query else None
        try:
            if request.args.get('all'):
                page = pageSize = None
            else:
                count = project_app(requestObj=querySet).project_count()
                if count % pageSize == 0:
                    totalPage = count // pageSize if count != 0 else 1
                else:
                    totalPage = (count // pageSize) + 1
                if page > totalPage:
                    return raise_status(400, '页数超出范围')
            projects_list = project_app(requestObj=querySet).project_find_all(page, pageSize)
        except Exception as e:
            logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
            return '后台异常', 500
        project_ln_list = []
        for project_model in projects_list:
            if project_model.base is None:
                base = None
            else:
                if request.args.get('embed'):
                    if project_model.base.base is None:
                        base_reference = None
                    else:
                        base_reference = str(project_model.base.base._id)
                    base = {
                        'id': str(project_model.base._id),
                        'creator': str(project_model.base.creator),
                        'description': project_model.base.description,
                        'requirement': project_model.base.requirement,
                        'title': project_model.base.title,
                        'material': project_model.base.material,
                        'tag': project_model.base.tag.name,
                        'timeConsume': project_model.base.timeConsume,
                        'labs': project_model.base.labs,
                        'reference': project_model.base.reference,
                        'image': project_model.base.image,
                        'base': base_reference,
                        'spec': project_model.base.spec,
                        'createdAt': project_model.base.createdAt,
                        'updatedAt': project_model.base.updatedAt
                    }
                else:
                    base = str(project_model.base._id)
            data = {
                'id': str(project_model._id),
                'creator': str(project_model.creator),
                'description': project_model.description,
                'requirement': project_model.requirement,
                'title': project_model.title,
                'material': project_model.material,
                'labs': project_model.labs,
                'reference': project_model.reference,
                'tag': project_model.tag.name,
                'timeConsume': project_model.timeConsume,
                'image': project_model.image,
                'base': base,
                'spec': project_model.spec,
                'createdAt': project_model.createdAt,
                'updatedAt': project_model.updatedAt
            }
            project_ln_list.append(data)
        if not request.args.get('all'):
            meta = {'page': page, 'pageSize': pageSize, 'total': count, 'totalPage': totalPage}
            returnObj = {'projects': project_ln_list, 'meta': meta}
        else:
            returnObj = {
                'projects': project_ln_list
            }
        return jsonify(returnObj)
    except Exception as e:
        logging.error('error id: %s' % i)
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return raise_status(500, '后台异常')


@projects.route('/projects/<projectId>', methods=['GET'])
def get_project(projectId):
    from application.project_app import project_app
    from model import PROJECT
    from bson import ObjectId
    # fields = request.args.get('field')
    try:
        projectId = ObjectId(projectId)
        project_app().projectId_check(projectId=projectId)
    except PROJECT.DoesNotExist:
        return raise_status(400, '无效的项目')
    except Exception as e:
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return raise_status(400, '错误的ObjectId')
    requestObj = {'_id': projectId}
    project = project_app(requestObj=requestObj).project_find_one()
    if project.base == None:
        base = None
    else:
        if request.args.get('embed'):
            if project.base.base is None:
                base_reference = None
            else:
                base_reference = str(project.base.base._id)
            base = {
                'id': str(project.base._id),
                'creator': str(project.base.creator),
                'description': project.base.description,
                'requirement': project.base.requirement,
                'title': project.base.title,
                'tag': project.base.tag.name,
                'timeConsume': project.base.timeConsume,
                'labs': project.base.labs,
                'material': project.base.material,
                'reference': project.base.reference,
                'image': project.base.image,
                'base': base_reference,
                'spec': project.base.spec,
                'createdAt': project.base.createdAt,
                'updatedAt': project.base.updatedAt
            }
        else:
            base = str(project.base._id)
    data = {
        'id': str(project._id),
        'creator': str(project.creator),
        'description': project.description,
        'requirement': project.requirement,
        'material': project.material,
        'title': project.title,
        'tag': project.tag.name,
        'labs': project.labs,
        'reference': project.reference,
        'timeConsume': project.timeConsume,
        'image': project.image,
        'base': base,
        'spec': project.spec,
        'createdAt': project.createdAt,
        'updatedAt': project.updatedAt
    }
    return jsonify(data)


@projects.route('/projects/<projectId>', methods=['PUT'])
def project_replace(projectId):
    from application.project_app import project_app
    from model import PROJECT
    from bson import ObjectId

    try:
        projectId = ObjectId(projectId)
        project_app().projectId_check(projectId=projectId)
    except PROJECT.DoesNotExist:
        return raise_status(400, '无效的项目')
    except Exception as e:
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return raise_status(400, '错误的ObjectId')
    requestObj = {'_id': projectId}
    updateObj = request.json
    query_list = ['creator', 'title', 'description', 'requirement', 'timeConsume',
                  'material', 'reference', 'image', 'base', 'spec', 'tag']
    updateObj = filter(query_list=query_list, updateObj=updateObj)
    if updateObj.get('id'):
        del updateObj['id']
    try:
        if updateObj.get('base') and updateObj.get('base') is not None:
            updateObj['base'] = ObjectId(updateObj['base'])
            project_app().project_reference_check(reference=updateObj['base'])
    except PROJECT.DoesNotExist:
        return raise_status(400, '引用错误')
    try:
        project_app(requestObj=requestObj, updateObj=updateObj).project_update_set()
        project = project_app(requestObj=requestObj).project_find_one()
    except Exception as e:
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return '后台异常', 500
    if project._id == project.base:
        baseId = None
    else:
        if project.base is None:
            baseId = project.base
        else:
            baseId = str(project.base._id)
    returnObj = {
        'id': str(project._id),
        'creator': str(project.creator),
        'title': project.title,
        'description': project.description,
        'requirement': project.requirement,
        'material': project.material,
        'labs': project.labs,
        'tag': project.tag.name,
        'timeConsume': project.timeConsume,
        'reference': project.reference,
        'image': project.image,
        'base': baseId,
        'spec': project.spec,
        'createdAt': project.createdAt,
        'updatedAt': project.updatedAt
    }
    return jsonify(returnObj)


@projects.route('/projects/<projectId>', methods=['PATCH'])
def project_change(projectId):
    from application.project_app import project_app
    from model import PROJECT
    from bson import ObjectId

    try:
        projectId = ObjectId(projectId)
        project_app().projectId_check(projectId=projectId)
    except PROJECT.DoesNotExist:
        return jsonify({'error': raise_status(400, 'projectIdError')})
    except Exception as e:
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return jsonify({'error': raise_status(400, 'ObjectIdError')})
    requestObj = {'_id': projectId}
    updateObj = request.json
    query_list = ['creator', 'title', 'description', 'requirement', 'timeConsume',
                  'material', 'reference', 'image', 'base', 'spec', 'tag']
    updateObj = filter(query_list=query_list, updateObj=updateObj)
    if updateObj.get('id'):
        del updateObj['id']
    try:
        if updateObj.get('base') and updateObj.get('base') != projectId:
            updateObj['base'] = ObjectId(updateObj['base'])
            project_app().project_reference_check(reference=updateObj['base'])
    except PROJECT.DoesNotExist:
        return jsonify({'error': raise_status(400, 'referenceError')})
    try:
        project_app(requestObj=requestObj, updateObj=request.json).project_update_set()
        project = project_app(requestObj=requestObj).project_find_one()
    except Exception as e:
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return '后台异常', 500
    if project._id == project.base:
        baseId = None
    else:
        baseId = str(project.base._id)
    returnObj = {
        'id': str(project._id),
        'creator': str(project.creator),
        'title': project.title,
        'description': project.description,
        'requirement': project.requirement,
        'material': project.material,
        'reference': project.reference,
        'tag': project.tag.name,
        'labs': project.labs,
        'timeConsume': project.timeConsume,
        'image': project.image,
        'base': baseId,
        'spec': project.spec,
        'createdAt': project.createdAt,
        'updatedAt': project.updatedAt
    }
    return jsonify(returnObj)


@projects.route('/projects/<projectId>', methods=['DELETE'])
def project_delete(projectId):
    from application.project_app import project_app
    from model import PROJECT
    from auth import raise_status
    from bson import ObjectId

    try:
        projectId = ObjectId(projectId)
        project_app().projectId_check(projectId=projectId)
        requestObj = {'_id': projectId}
        project_app(requestObj=requestObj).project_delete()
    except PROJECT.DoesNotExist:
        return raise_status(400, '无效的项目')
    except Exception as e:
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return jsonify({'error': raise_status(400, '错误的ObjectId')})
    return raise_status(200)


@projects.route('/projects/tag', methods=['GET'])
def project_tag():
    from model import CATEGORY, TYPE, PROJECT
    try:
        category_model_list = list(CATEGORY.objects.raw({'delete': False}))
    except Exception as e:
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return raise_status(500, '后台异常')
    tag_list = []
    for model in category_model_list:
        category = {'id': str(model._id), 'category': model.name}
        try:
            type_list = list(TYPE.objects.raw({'category': model._id, 'delete': False}))
        except Exception as e:
            logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
            return raise_status(500, '后台异常')
        tag = []
        for type_model in type_list:
            count = PROJECT.objects.raw({'tag': type_model._id, 'delete': False}).count()
            tag.append({
                'id': str(type_model._id),
                'name': type_model.name,
                'count': count
            })
        category['type'] = tag
        tag_list.append(category)
    return jsonify(tag_list)


@projects.route('/project/management', methods=['GET'])
def project_management():
    from application.project_app import project_app
    sort = request.args.get('sort', [])
    search = request.args.get('search', [])
    filt = request.args.get('filter')
    status = request.args.get('all')
    page = int(request.args.get('page', 1)) if not status else None
    pageSize = int(request.args.get('pageSize', 20)) if not status else None
    order = ()
    for x in sort:
        order += [x, 1]
    requestObj = {}
    for x in search:
        requestObj = dict(requestObj, **x)
    # 存在过滤数组
    if filt:
        requestObj['_id'] = {'$nin': [ObjectId(x) for x in filt]}
    # 此时总数已经考虑了过滤数组
    try:
        count = project_app(requestObj=requestObj).project_count()
        model_list = project_app(requestObj=requestObj).project_find_many_by_order(page=page, pageSize=pageSize,
                                                                                   order=order)
    except Exception as e:
        logging.error('Request Error: {}\nStack: {}\n'.format(e, traceback.format_exc()))
        return '后台异常', 500
    # 只返回需要数据，_id、title、creator
    returnObj = []
    for model in model_list:
        returnObj.append({
            'id': str(model._id),
            'title': model.title,
            'creator': str(model.creator)
        })
    return jsonify({'count': count, 'returnObj': returnObj})
