# -*- coding: utf-8 -*-
# @Time    : 2021/4/6 1:30
# @Author  : Longbiu
# @Email   : longbiu@foxmail.com
# @File    : serializer.py
# @Software: PyCharm
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

import goods
from goods.models import Goods
from libs.iPay.test import subject
from trade import models


class OrderSerializer(serializers.ModelSerializer):
    # 要支持单购物和群购物(购物车)，前台要提交 课程主键(们)
    goods = serializers.PrimaryKeyRelatedField(queryset=Goods.objects.all(), write_only=True, many=True)

    class Meta:
        model = models.Order
        fields = ('subject', 'total_amount', 'pay_type', 'goods')
        extra_kwargs = {
            'total_amount': {
                'required': True
            },
            'pay_type': {
                'required': True
            },
        }

    def _check_total_amount(self, attrs):
        total_amount = attrs.get('total_amount')
        goods_list = attrs.get('goods')
        total_price = 0
        for goods in goods_list:
            total_price+=goods.goods_price
        if total_price!=total_amount:
            raise ValidationError('价格不合法')
        return total_amount

    def validate(self, attrs):
        total_amount = self._check_total_amount(attrs)
        out_trade_no = self._get_out_trade_no()
        user = self._get_user()
        pay_url = self._get_pay_url(out_trade_no, total_amount, attrs.get('subject'))
        self._before_create(attrs, user,pay_url)
        return attrs

    def _get_out_trade_no(self):
        import uuid
        return str(uuid.uuid4()).replace('-','')

    def _get_user(self):
        request = self.context.get('request')
        return request.user

    def _get_pay_url(self, out_trade_no, total_amount, subject):
        from libs import iPay
        order_string = iPay.alipay.api_alipay_trade_page_pay(
            out_trade_no=out_trade_no,
            total_amount=float(total_amount),  # 只有生成支付宝链接时，不能用Decimal
            subject=subject,
            return_url=settings.RETURN_URL,
            notify_url=settings.NOTIFY_URL,
        )
        pay_url = iPay.gateway + '?' + order_string
        # 将支付链接存入，传递给views
        self.context['pay_url'] = pay_url

    def _before_create(self, attrs, user, out_trade_no):
        attrs['user'] = user
        attrs['out_trade_no'] = out_trade_no

    def create(self, validated_data):
        goods_list = validated_data.pop('goods')
        order = models.Order.objects.create(**validated_data)
        for goods in goods_list:
            models.OrderDetail.objects.create(order=order,goods=goods)
        return order