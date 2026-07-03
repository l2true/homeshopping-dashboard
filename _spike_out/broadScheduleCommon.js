;(function($,win){
	let scheduleCommon = function(){
		let cls = this;
		cls.deviceChecker = $('#MCDeviceChecker').data('devicechecker');
		cls.isApp = cls.deviceChecker.app;
		cls.searchLayer = '#gs-md-srch';
		cls.mseqPrefix = {
			app : 'A00323'
			, web : 'W00323'
		};
		cls.timerDiffTimes = new Array();
		cls.timerIntervals = new Array();
		// cls.broadContentsArea = '#broadSchedule';
		cls.option = {
			contentId : $('#main_area').size() == 0 ? '#cont_wrap' : '#main_area'
			, mseqFix : {}
			, mseqObj : {}
		}

		cls.broadType = '';
		cls.initData = function(param){
			if(null != param){
				cls.option = 'undefined' != typeof param
					? $.extend(cls.option, param) : cls.option;
				cls.broadType = 'undefined' != typeof param
					? param.broadType : '';
			}
		}

		cls.init = function() {
			// cls.initData();
			cls.setEvent();
		}

		cls.setEvent = function() {
			cls.setOnAirTimer();
			cls.moreViewPrd(); // 부상품 더보기/닫기

			// 라이브톡/마이샵톡
			$(`${cls.option.contentId} [name=btnLiveTalk]`).off('click').on('click', function(e) {
				e.stopPropagation();
				cls.setSessionStorage();
				let params = {};
				params.isOnair = true;
				params.gbn = 'LIVETALK';
				gsCommon.sendClickTrac({ mseq : window.scheduleCommon.setMseq(params)});
				let url = `https://${window.location.host}/section/livetalk`;
				if($(this).hasClass('myshop')){
					url = `https://${window.location.host}/section/dataBrd/livetalk`;
				}
				location.href = url;
			});



			// 편성표 검색 레이어 내 상품 클릭
			$(`${cls.option.contentId} .prd-item .prd-link`).off('click').on('click', function(e){
				e.stopPropagation();
				// cls.setSessionStorage();
			});

			// 바로구매 처리
			$(`${cls.option.contentId} [name=btnOrd]`).off('click').on('click', function(e) {
				let channel = $(this).closest('.prd-group.typeB').data('broadcast');
				let isDeal = $(this).data('isdeal') == 'Y';
				// 샤피라이브면서 딜이 아닌 경우에만 샤피라이브 구매하기
				if(channel == 'shoppy') {
					// if(isDeal) {
					// 	let prdCd = $(this).data('prdcd');
					// 	cls.directOrderTvBroadCast.call($(this), e, prdCd, isDeal, true);
					// } else {
						cls.directOrderShoppy.call($(this), e);
					// }
				} else {
					let prdCd = $(this).parents(".prd-item").data("prdcd");
					cls.directOrderTvBroadCast.call($(this), e, prdCd);
				}
			});

			// LIVE/DATA 방송 알림
			$(`${cls.option.contentId} .prd-group.typeB [name=btnBroadAlarm]`).off('click').on('click', function(e) {
				e.stopPropagation();
				let broadCastGbn = $(this).closest('.prd-group.typeB').data('broadcast');
				let gbnParam = {
					alarmOn : 'MAIN_ALARM_ON'
					, alarmOff : 'MAIN_ALARM_OFF'
					, broadCastGbn : broadCastGbn
					, isOnair : $(this).data('live') == 'Y'
					, isSearchYn : cls.option.contentId == '#cont_wrap' ? 'Y' : 'N'
				}
				cls.broadAlarmLiveAndData.call($(this), e, gbnParam);

				// 편성표 검색 레이어에도 같은 상품 존재하는 경우 방송 알림 on/off 처리
				let prdCd = $(this).closest('.prd-item').data('prdcd');
				let layerTarget = $(`${cls.searchLayer} [name=btnBroadAlarm][data-prdcd=${prdCd}]`);
				cls.setBroadAlarmOnOff(layerTarget);
			});

			// SHOPPY 방송 알림
			$(`${cls.option.contentId} [name=btnSpBroadAlarm]`).off('click').on('click', function (e) {
				e.stopPropagation();
				let broadCastGbn = $(this).closest('.prd-group.typeB').data('broadcast');
				let gbnParam = {
					alarmOn : 'SHOPPY_ALARM_ON'
					, alarmOff : 'SHOPPY_ALARM_OFF'
					, broadCastGbn : broadCastGbn
					, isOnair : $(this).data('live') == 'Y'
					, isSearchYn : cls.option.contentId == '#cont_wrap' ? 'Y' : 'N'
				}
				cls.broadAlarmShoppy.call($(this), e, gbnParam);

				// 편성표 검색 레이어에도 같은 상품 존재하는 경우 방송 알림 on/off 처리
				let prdCd = $(this).data('prdcd');
				let layerTarget = $(`${cls.searchLayer} [name=btnBroadAlarm][data-prdcd=${prdCd}]`);
				cls.setBroadAlarmOnOff(layerTarget);
			});
		}

		cls.setBroadAlarmOnOff = function(target) {
			if (target.length > 0) {
				if (target.hasClass('on')) {
					$(target).removeClass('on');
				} else {
					$(target).addClass('on');
				}
			}
		}

		cls.broadAlarmLiveAndData = function(e, gbnParam) {
			let isOn = $(this).hasClass('on');
			if (gbnParam) {
				let params = {};
				params.isOnair = gbnParam['isOnair'];
				params.gbn = !isOn ? gbnParam['alarmOn'] : gbnParam['alarmOff'];
				if("ALL" === cls.broadType){
					params.broadCastGbn = 'undefined' != typeof gbnParam['broadCastGbn'] ? gbnParam['broadCastGbn'] : '';
				}
				gsCommon.sendClickTrac({mseq: cls.setMseq(params)});
			}

			if (!isOn) {
				let $target = $(this).closest('.prd-item');
				let prdId = $target.data('prdcd');
				let prdNm = $target.find('.prd-name').text();
				let broadType = cls.option.contentId == '#broadSchedule'
					? $(this).closest('.prd-group.typeB').data('broadcast') : $(this).closest('.prd-item').data('broadtype');
				// broadAlarm.js 참조
				let returnUrl = cls.getReturnUrl(gbnParam['isSearchYn']);
				broadAlarm.setPrdInfo(prdId, prdNm, returnUrl);
				broadAlarm.setTarget($(this));
				// broadAlarm.setBroadType($('a.a-toggle.on')[0].classList[1]);
				broadAlarm.setBroadType(cls.getBroadCastChannel(broadType));
				broadAlarm.broadAlarmClickEvent(e);
			} else {
				broadAlarmDeleteByPrdId($(this).closest('.prd-item').data('prdcd'), $(this));
			}
		}

		cls.broadAlarmShoppy = function(e, gbnParam) {
			let prdCd = $(this).data('prdcd');
			let prdName = $(this).closest('.live-item').find('.prd-name').text();
			let returnUrl = cls.getReturnUrl(gbnParam['isSearchYn']);
			broadAlarm.setMobileLivePrdInfo(prdCd, returnUrl, $(this));	//샤피 상품
			let params = {};
			// params.isOnair = $(this).data('live') == 'Y';
			params.isOnair = gbnParam['isOnair'];
			if ($(this).hasClass("on")) {
				mobileLivePrdAlarmDelete(prdCd);
				params.gbn = gbnParam['alarmOff'];
			} else {
				broadAlarm.mobileLiveAlarmClickEvent(e);
				params.gbn = gbnParam['alarmOn'];
			}
			if("ALL" === cls.broadType){
				params.broadCastGbn = 'undefined' != typeof gbnParam['broadCastGbn'] ? gbnParam['broadCastGbn'] : '';
			}
			if(gbnParam) {
				gsCommon.sendClickTrac({ mseq : cls.setMseq(params) });
			}
		}

		/**
		 * 앱 여부에 따른 return url을 셋팅
		 * @param isSearchYn    'Y' 인 경우 편성표 검색에서 진입
		 */
		cls.getReturnUrl = function(isSearchYn) {
			if (cls.isApp && 'Y' == isSearchYn) {
				// 앱 편성표 검색인 경우 : 편성표 레이어 초기 화면
				return '/main/broadSchedule/search.gs?gbn=init';
			}
			// 그 외 : 편성표 탭 매장
			return '/index.gs?tabId=323';
		}

		/**
		 * SHOPPY 바로구매
		 * @param e
		 */
		cls.directOrderShoppy = function() {
			let liveNo = $(this).closest('.prd-item').data('liveno');
			let prdCd = $(this).data('prdcd');
			let isDeal = $(this).data('isdeal');
			let url = new URL($(this).data('linkurl'));
			let urlParams = url.searchParams;
			let mseq = urlParams.get('mseq');
			shoppyDirectOrd.processDirectOrd(liveNo, mseq);

			const clickTracParams = {
				liveNo: liveNo,
				directOrd: 'Y',
				mseq: mseq
			};

			if (isDeal === 'Y') {
				// 딜인 경우 dealNo를 파라미터로 넘김
				clickTracParams.dealNo = prdCd;
			} else {
				// 상품인 경우 prdCd를 파라미터로 넘김
				clickTracParams.prdCd = prdCd;
			}
			gsCommon.sendClickTrac(clickTracParams);
		}

		/**
		 * LIVE/DATA 바로구매
		 * @param e
		 */
		cls.directOrderTvBroadCast = function(e, prdCd, isDeal, isShoppyShop) {
			e.stopPropagation();
			// let prdCd = $(this).data("prdcd");
			// let prdCd = $(this).parents(".prd-item").data("prdcd");
			let linkUrl = $(this).data("linkurl");
			// 편성표 검색 데이터인 경우, 앱에서 구매하기 동작 분기를 위한 파라미터 추가(isSchedule=Y)
			let isSchedule = cls.option.contentId == '#cont_wrap' ? 'Y' : 'N';

			if (cls.isApp && window.flutter_inappwebview) {
				linkUrl = linkUrl +"?imgSrc="+encodeURIComponent($(this).closest('.prd-item').find('img').attr("src").replace('_B1','_O1'));
				linkUrl = linkUrl +"&prdNm="+encodeURIComponent($(this).closest('.prd-item').find('.prd-name').html());
				linkUrl = linkUrl + '&prdLink='+encodeURIComponent($(this).closest('.prd-item').find('.prd-link').attr('href'));
			}

			if ("Y" == $(this).data("multipageyn") || -1 == $(this).data("linkurl").indexOf("direct") || "N" == $(this).data("salepsbl")) {
				location.href = linkUrl;
			} else {
				cls.directOrd(linkUrl, prdCd, "N", isDeal, isShoppyShop, isSchedule);
			}
		}

		cls.directOrd = function(linkUrl, prdCd, basktOnly, isDeal, isShoppyShop, isSchedule) {
			let oldFlg = false;
			try {
				if (cls.deviceChecker.android) {
					let parser = new UAParser();
					let os = parser.getOS();
					oldFlg = os.name == "Android" && Number(os.version.split(".")[0]) < 5;
				}
			} catch(e) {}
			if ("" != linkUrl && "#" != linkUrl && "undefined" != typeof prdCd) {
				// cls.setSessionStorage();

				if (cls.isApp) {
					let url;
					if (window.flutter_inappwebview) {
						url = `toapp://directord?${linkUrl}`;
					} else if (cls.deviceChecker.UAgentAppVer >= 198 && !oldFlg) {
						url = `toapp://directOrd?http://${window.location.host}/shop/directOrd/${prdCd}` ;
					} else {
						url = `toapp://directOrd?http://${window.location.host}/prd/directOrd/${prdCd}`;
					}
					if('Y' == isSchedule) {
						window.location.href = `${url}?isSchedule=${isSchedule}`;
					}
				} else {
					if (oldFlg) {
						directOrd.open($(this).data("linkurl"));
					} else {
						// try {
						// 	if(cmmDirectOrd.directOrd != null && cmmDirectOrd.directOrd.option.ordParam.isDeal != isDeal){
						// 		if(cmm.prdOrder){
						// 			cmm.prdOrder.option.isDeal=isDeal;
						// 			cmm.prdOrder.paramData.isDeal=isDeal;
						// 			cmm.prdOrder.option.isShoppyShop=isShoppyShop;
						// 			cmm.prdOrder.paramData.isShoppyShop=isShoppyShop;
						// 		}
						// 		cmmDirectOrd.directOrd = null;
						// 	}
						// } catch (e) {
						// 	cmmDirectOrd.directOrd = null;
						// }

						let mseq = gsCommon.getParam(linkUrl, "mseq");
						mseq = (typeof mseq == "undefined") ? "" : mseq;

						let pgmID = gsCommon.getParam(linkUrl, "pgmID");
						pgmID = (typeof pgmID == "undefined") ? "" : pgmID;

						let uri = (typeof commonStaticUri != "undefined") ? commonStaticUri : null;
						cmmDirectOrd.processDirectOrd(uri, prdCd, "N", isDeal, isShoppyShop);
						if (mseq != "") { gsCommon.sendClickTrac({mseq : mseq, prdCd : prdCd, pgmID:pgmID, directOrd : "Y" });}
					}
				}
			}

		}

		/**
		 * 부상품 더보기 동작 이벤트
		 */
		cls.moreViewPrd = function() {
			let itemGroup = document.querySelectorAll('.prd-group');

			if (itemGroup.length) {
				itemGroup.forEach(function(el){
					let accordion = el.querySelector('.accordion-type');
					let moreBtn = el.querySelector('.more-view');
					let params = {};
					if("ALL" === cls.broadType){
						params.broadCastGbn = $(el).closest('.prd-group.typeB').data('broadcast');
					}
					params.isOnair = true;
					if(moreBtn && accordion) {
						let hiddenItems = accordion.querySelectorAll('.none');

						$(moreBtn).off('click').on('click', function(e) {
							if (!el.classList.contains('on')){
								el.classList.add('on');
								hiddenItems.forEach((item) => item.classList.remove('none'));
								params.gbn = 'MORE_OPEN';
							}else {
								el.classList.remove('on');
								hiddenItems.forEach((item) => item.classList.add('none'));
								params.gbn = 'MORE_CLOSE';
							}
							gsCommon.sendClickTrac({mseq: cls.setMseq(params)});
							
							const span = moreBtn.querySelector('span');
						    const em = span.querySelector('em');

						    // 현재 상태 확인
						    const isMoreView = span.textContent.includes('더보기');

						    if (isMoreView) {
						      // 더보기 -> 닫기
						      span.innerHTML = '';
						      if (em) span.appendChild(em);
						      span.insertAdjacentText('beforeend', '상품 닫기');
						    } else {
						      // 닫기 -> 더보기
						      span.innerHTML = '';
						      if (em) span.appendChild(em);
						      span.insertAdjacentText('beforeend', '상품 더보기');
						    }
						});
						
						
					}
				});
			}
		}

		/**
		 * <pre>
		 * 생방송 남은시간 타이머 설정
		 * </pre>
		 */
		cls.setOnAirTimer = function(){
			let onAirSchedules = document.querySelectorAll('.prd-group.onair');
			if(onAirSchedules.length > 0){
				for (let index=0; index<onAirSchedules.length; index++) {
					let broadType = onAirSchedules[index].dataset.broadcast;
					// 샤피라이브인 경우 동시방송 여부에 따라 남은시간을 다르게 노출
					if(broadType == 'shoppy') {
						cls.setShoppyOnAirTimer(onAirSchedules, index);
					} else {
						// LIVE/DATA 방송
						let broadEndDate = onAirSchedules[index].querySelector('.prd-group.typeA').dataset.broadenddate;
						let tvBroad = onAirSchedules[index];
						cls.mainTvBroadDateCheckInit(broadEndDate, index, tvBroad);
					}
				}
			}

			//부상품 방송 정보 제거
			// $('.prd-list_horizon .badge-vod').hide();
			// $('.prd-list_horizon .broadcast').hide();
		}

		/**
		 * 샤피라이브 생방송 타이머 설정
		 * @param onAirSchedules
		 * @param index
		 */
		cls.setShoppyOnAirTimer = function(onAirSchedules, index) {
			let shoppyBroads = onAirSchedules[index].querySelectorAll('.prd-item.horizon.mix');
			let isSimulCast = shoppyBroads.length > 1;
			if(isSimulCast) {
				// 동시방송인 경우
				for (let i=0; i<shoppyBroads.length; i++) {
					let broadEndDate = shoppyBroads[i].dataset.broadenddate;
					cls.mainTvBroadDateCheckInit(broadEndDate, index+i, shoppyBroads[i], isSimulCast);
				}
			} else {
				// 동시방송 아닌 경우
				let broadEndDate = shoppyBroads[0].dataset.broadenddate;
				cls.mainTvBroadDateCheckInit(broadEndDate, index, onAirSchedules[index]);
			}
		}

		/**
		 * <pre>
		 * 생방송 남은 시간 초기설정
		 * </pre>
		 * @param pgmInfo json 포맷
		 */
		cls.mainTvBroadDateCheckInit = function(nextBroadDate, index, target, isSimulCast) {
			if('undefined' != nextBroadDate){
				if(cls.timerIntervals[index] != null){
					clearTimeout(cls.timerIntervals[index]);
				}

				let nextTime = nextBroadDate;
				let tvStartTime	= new Date();
				let tvEndTime= new Date(eval(nextTime.substring(0,4)), eval(parseInt(nextTime.substring(4,6), 10) - 1), eval(nextTime.substring(6,8)), eval(nextTime.substring(8,10)), eval(nextTime.substring(10,12)), eval(nextTime.substring(12)));
				cls.timerDiffTimes[index] = parseInt(((tvEndTime.getTime() - tvStartTime.getTime())/1000)+0.999,10);

				if (cls.timerDiffTimes[index] > 0) {
					cls.mainTvBroadDateCheck(index, target, isSimulCast);
				} else {
					cls.onAirTimeCount('E', '', target, isSimulCast);
					clearTimeout(cls.timerIntervals[index]);
				}
			}
		}

		/**
		 * <pre>
		 * 생방송 남은 시간 실시간 체크 및 표시
		 * </pre>
		 */
		cls.mainTvBroadDateCheck = function(index, target, isSimulCast){
			tmpTime	= cls.timerDiffTimes[index];								// 초계산
			viewSec	= tmpTime % 60;
			if(viewSec < 10){viewSec="0" + viewSec;}				// 이부분은 초단위에 한자리 숫자일때 앞에 0을 포함시키는것

			tmpTime		= parseInt(tmpTime / 60, 10);				// 분계산
			viewMinute	= tmpTime % 60;
			if(viewMinute<10){viewMinute="0" + viewMinute;}			// 이부분은 분단위에 한자리 숫자일때 앞에 0을 포함시키는것

			tmpTime		= parseInt(tmpTime / 60, 10);				// 시계산
			viewHours	= tmpTime % 24;
			if(viewHours<10){viewHours="0" + viewHours;}				// 이부분은 시단위에 한자리 숫자일때 앞에 0을 포함시키는것

			tmpTime		= parseInt(tmpTime / 24, 10);				// 일수계산
			viewDay		= tmpTime % 12;

			// 남은시간 노출
			let remainTime = !isSimulCast && '00' == viewHours ? `${viewMinute}:${viewSec}` : `${viewHours}:${viewMinute}:${viewSec}`;
			let gbn = '00' == viewHours && '00' == viewMinute && '00' == viewSec ? 'E' : 'S';
			cls.onAirTimeCount(gbn, remainTime, target, isSimulCast);

			cls.timerDiffTimes[index] -= 1;
			if (cls.timerDiffTimes[index] < 0) {
				if(cls.timerIntervals[index] != null){
					clearTimeout(cls.timerIntervals[index]);
				}
			} else {
				cls.timerIntervals[index] = setTimeout(function(){cls.mainTvBroadDateCheck(index, target, isSimulCast)}, 1000);
			}
		}

		/**
		 * <pre>
		 * onAir 영역 남은시간 카운트 처리
		 * </pre>
		 * @param gbn 'E' 방송종료, 'S' 남은시간
		 * @param remainTime 남은시간 00:00:00
		 * @param target 남은시간 노출할 타겟 element
		 */
		cls.onAirTimeCount = function(gbn, remainTime, target, isSimulCast){
			if('E' == gbn){
				let todayTarget = $('.day-item.today');
				// 방송종료
				cls.isOnAirCount = true;
				target.querySelector('.remain-time').innerText = '';
			}else if('S' == gbn){
				// 생방송 남은시간
				if(isSimulCast || "shoppy" === $(target).data('broadcast')) { // 샤피 방송 이미지 내 시간 임시 처리, 동시방송, 단일방송 동일
					target.querySelector('.remain-time').innerText = remainTime;
				} else {
					target.querySelector('.remain-time em').innerText = remainTime;
				}
			}
		}

		// 방송 타입에 따른 방송알림용 방송 채널 값 반환
		cls.getBroadCastChannel = function(broadType) {
			if('LIVE' == broadType || 'L' == broadType || 'T' == broadType) {
				return 'live';
			} else if('DATA' == broadType || 'D' == broadType) {
				return 'myshop';
			} else {
				return 'empty';
			}
		}

		/**
		 * <pre>
		 * mseq 설정
		 * </pre>
		 * @param params isOnair : 생방송구분, gbn : 구분자, idx : 인덱스
		 */
		cls.setMseq = function(params){
			// let onAirGbn = 'undefined' != typeof params.isOnair ? (params.isOnair ? cls.option.mseqFix["LIVE"] : cls.option.mseqFix["ETC"]) : '';
			let onAirGbn = 'undefined' != typeof params.isOnair ? cls.option.mseqFix["LIVE"] : '';
			let broadCastGbn = ''; // 전체 탭일 경우
			if(params.broadCastGbn){
				if("LIVE" === params.broadCastGbn){
					broadCastGbn = "_LIVE";
				}else if("DATA" === params.broadCastGbn){
					broadCastGbn = "_MYSHOP";
				}else if("shoppy" === params.broadCastGbn){
					broadCastGbn = "_MLIVE";
				}
			}
			if('undefined' != typeof cls.option.mseqObj && 'undefined' != typeof cls.option.mseqObj[params.gbn]) {
				let sectionSeq = cls.option.contentId == '#main_area' ? gsCommon.getParam($('#main_area').attr('data-section-url'), 'mseq') : cls.getMseqPrefix();
				let mseq = sectionSeq.concat(onAirGbn).concat(broadCastGbn).concat(cls.option.mseqObj[params.gbn]);
				if('undefined' != typeof params.idx){
					mseq = mseq.concat(params.idx);
				}
				return mseq;
			}else{
				return '';
			}
		}

		cls.getMseqPrefix = function() {
			return cls.isApp ? cls.mseqPrefix['app'] : cls.mseqPrefix['web'];
		}

		/**
		 * <pre>
		 * 세션스토리지 설정
		 * </pre>
		 */
		cls.setSessionStorage = function(){
			gsCommon.setStorageUsingCache('broadSchedule.contents', $(cls.option.contentId).html());
			gsCommon.setStorageUsingCache('broadSchedule.scrollY', gsCommon.getScrollNowY());
			gsCommon.m_storage.setItem('index.pageIdx', 1);
		}

		/**
		 * <pre>
		 * 세션스토리지 제거
		 * </pre>
		 */
		cls.removeSessionStorage = function(){
			gsCommon.removeStorageOfCurrentPage("broadSchedule.scrollY");
			gsCommon.removeStorageOfCurrentPage("broadSchedule.contents");
			gsCommon.m_storage.removeItem("index.pageIdx");
		}
		return cls;
	}

	window.scheduleCommon = new scheduleCommon();
	window.scheduleCommon.init();
})(jQuery, window);